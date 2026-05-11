interface Env {
  POSTS_KV: KVNamespace;
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_ADMIN_CHAT_ID: string;
  INSTAGRAM_ACCESS_TOKEN: string;
  INSTAGRAM_USER_ID: string;
  WORKER_SHARED_SECRET: string;
}

type PostStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "published"
  | "expired"
  | "failed";

interface GeneratedPost {
  post_id: string;
  status: PostStatus;
  topic: string;
  slot: string;
  headline: string;
  image_prompt: string;
  image_alt_text: string;
  caption: string;
  hashtags: string[];
  sources: Array<{ title: string; url: string; publisher?: string }>;
  r2_object_key?: string;
  r2_image_url?: string;
  // Carousel: list of image URLs (cover at [0]). When length > 1, this
  // is published as IG CAROUSEL_ALBUM. Single posts have length 0 or 1.
  image_urls?: string[];
  slide_titles?: string[];
  telegram_message_id?: number;
  instagram_media_id?: string;
  created_at: string;
  approved_at?: string;
  published_at?: string;
  error_log?: string;
}

interface TelegramCallbackQuery {
  id: string;
  from: { id: number };
  message?: {
    message_id: number;
    chat: { id: number };
  };
  data?: string;
}

interface TelegramUpdate {
  callback_query?: TelegramCallbackQuery;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/api/posts") {
      return savePost(request, env);
    }

    if (request.method === "POST" && url.pathname === "/api/posts/expire") {
      return expirePosts(request, env);
    }

    if (request.method === "POST" && url.pathname === "/telegram/webhook") {
      return handleTelegramWebhook(request, env);
    }

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true });
    }

    return json({ error: "not_found" }, 404);
  },
};

async function savePost(request: Request, env: Env): Promise<Response> {
  const unauthorized = assertSharedSecret(request, env);
  if (unauthorized) return unauthorized;

  const post = (await request.json()) as GeneratedPost;
  const invalid = validatePost(post);
  if (invalid) return invalid;

  await env.POSTS_KV.put(postKey(post.post_id), JSON.stringify(post));
  await env.POSTS_KV.put(indexKey(post.created_at, post.post_id), post.post_id);
  return json({ ok: true, post_id: post.post_id });
}

async function expirePosts(request: Request, env: Env): Promise<Response> {
  const unauthorized = assertSharedSecret(request, env);
  if (unauthorized) return unauthorized;

  const body = (await request.json().catch(() => ({}))) as { max_age_hours?: number };
  const maxAgeHours = body.max_age_hours ?? 8;
  const cutoff = Date.now() - maxAgeHours * 60 * 60 * 1000;
  const list = await env.POSTS_KV.list({ prefix: "post:" });
  let expired = 0;

  for (const key of list.keys) {
    const post = await getPostByStorageKey(env, key.name);
    if (!post || post.status !== "pending_approval") continue;
    const created = Date.parse(post.created_at);
    if (Number.isFinite(created) && created < cutoff) {
      post.status = "expired";
      post.error_log = `Expired after ${maxAgeHours} hours without approval.`;
      await putPost(env, post);
      expired += 1;
      await sendTelegramMessage(
        env,
        `Expired pending post: ${post.headline}\nPost ID: ${post.post_id}`,
      );
    }
  }

  return json({ ok: true, expired });
}

async function handleTelegramWebhook(request: Request, env: Env): Promise<Response> {
  const update = (await request.json()) as TelegramUpdate;
  const callback = update.callback_query;
  if (!callback?.data) {
    return json({ ok: true, ignored: true });
  }

  const [action, postId] = callback.data.split(":");
  if (!postId) {
    await answerCallback(env, callback.id, "Invalid action payload.");
    return json({ ok: false, error: "invalid_payload" }, 400);
  }

  const post = await getPost(env, postId);
  if (!post) {
    await answerCallback(env, callback.id, "Post not found.");
    return json({ ok: false, error: "post_not_found" }, 404);
  }

  if (post.status !== "pending_approval") {
    await answerCallback(env, callback.id, `Post is already ${post.status}.`);
    return json({ ok: true, status: post.status });
  }

  if (action === "approve") {
    return approveAndPublish(env, callback, post);
  }

  if (action === "reject") {
    post.status = "rejected";
    await putPost(env, post);
    await answerCallback(env, callback.id, "Rejected.");
    await sendTelegramMessage(env, `Rejected: ${post.headline}\nPost ID: ${post.post_id}`);
    return json({ ok: true, status: post.status });
  }

  if (action === "regenerate_caption" || action === "regenerate_image") {
    await answerCallback(
      env,
      callback.id,
      "Regeneration is handled by rerunning the GitHub Action for now.",
    );
    await sendTelegramMessage(
      env,
      `Regeneration requested for ${post.post_id}. Rerun the GitHub Action manually for v1.`,
    );
    return json({ ok: true, status: post.status });
  }

  await answerCallback(env, callback.id, "Unknown action.");
  return json({ ok: false, error: "unknown_action" }, 400);
}

async function approveAndPublish(
  env: Env,
  callback: TelegramCallbackQuery,
  post: GeneratedPost,
): Promise<Response> {
  // Idempotency guard: if this post already published, do nothing.
  // Multiple click events on the same approval button (Telegram retries,
  // double-taps on mobile, network races) would otherwise create duplicate
  // IG posts and waste Graph API quota.
  if (post.status === "published" && post.instagram_media_id) {
    await answerCallback(env, callback.id, `Already published (IG ID ${post.instagram_media_id}).`);
    return json({
      ok: true,
      status: post.status,
      instagram_media_id: post.instagram_media_id,
      already_published: true,
    });
  }
  if (post.status === "approved") {
    // Approved but not yet published — likely a previous publish call is
    // mid-flight or failed silently. Retry, but mark the prior attempt.
    post.error_log = `Re-attempting publish at ${new Date().toISOString()}; prior error_log: ${post.error_log ?? "none"}`;
  }

  const carouselUrls = (post.image_urls ?? []).filter(Boolean);
  const singleUrl = post.r2_image_url;
  if (!singleUrl && carouselUrls.length === 0) {
    post.status = "failed";
    post.error_log = "Missing public image URL(s).";
    await putPost(env, post);
    await answerCallback(env, callback.id, "Failed: missing image URL.");
    return json({ ok: false, error: "missing_image_url" }, 400);
  }

  post.status = "approved";
  post.approved_at = new Date().toISOString();
  await putPost(env, post);
  await answerCallback(env, callback.id, "Approved. Publishing...");

  try {
    const instagramMediaId =
      carouselUrls.length > 1
        ? await publishCarouselToInstagram(env, post, carouselUrls)
        : await publishImageToInstagram(env, post, singleUrl ?? carouselUrls[0]);
    post.status = "published";
    post.instagram_media_id = instagramMediaId;
    post.published_at = new Date().toISOString();
    await putPost(env, post);
    await sendTelegramMessage(
      env,
      `Published${carouselUrls.length > 1 ? ` (carousel: ${carouselUrls.length} slides)` : ""}: ${post.headline}\nInstagram media ID: ${instagramMediaId}`,
    );
    return json({ ok: true, status: post.status, instagram_media_id: instagramMediaId });
  } catch (error) {
    post.status = "failed";
    post.error_log = error instanceof Error ? error.message : String(error);
    await putPost(env, post);
    await sendTelegramMessage(
      env,
      `Publish failed: ${post.headline}\nPost ID: ${post.post_id}\nError: ${post.error_log}`,
    );
    return json({ ok: false, error: post.error_log }, 502);
  }
}

async function publishImageToInstagram(
  env: Env,
  post: GeneratedPost,
  imageUrl: string,
): Promise<string> {
  const caption = captionForInstagram(post);
  const createUrl = `https://graph.facebook.com/v20.0/${env.INSTAGRAM_USER_ID}/media`;
  const createBody = new URLSearchParams({
    image_url: imageUrl,
    caption,
    access_token: env.INSTAGRAM_ACCESS_TOKEN,
  });
  const createResponse = await fetch(createUrl, { method: "POST", body: createBody });
  if (!createResponse.ok) {
    throw new Error(`Instagram media container failed: ${await createResponse.text()}`);
  }
  const container = (await createResponse.json()) as { id?: string };
  if (!container.id) {
    throw new Error("Instagram did not return media container id.");
  }

  return await publishContainerToInstagram(env, container.id);
}

async function publishCarouselToInstagram(
  env: Env,
  post: GeneratedPost,
  urls: string[],
): Promise<string> {
  // Step 1: create a child container per slide (is_carousel_item=true)
  const childIds: string[] = [];
  for (const url of urls) {
    const childUrl = `https://graph.facebook.com/v20.0/${env.INSTAGRAM_USER_ID}/media`;
    const childBody = new URLSearchParams({
      image_url: url,
      is_carousel_item: "true",
      access_token: env.INSTAGRAM_ACCESS_TOKEN,
    });
    const childResp = await fetch(childUrl, { method: "POST", body: childBody });
    if (!childResp.ok) {
      throw new Error(`Carousel child create failed for ${url}: ${await childResp.text()}`);
    }
    const child = (await childResp.json()) as { id?: string };
    if (!child.id) {
      throw new Error(`Carousel child returned no id for ${url}`);
    }
    childIds.push(child.id);
  }

  // Step 2: create carousel container that references the children
  const caption = captionForInstagram(post);
  const carouselUrl = `https://graph.facebook.com/v20.0/${env.INSTAGRAM_USER_ID}/media`;
  const carouselBody = new URLSearchParams({
    media_type: "CAROUSEL",
    children: childIds.join(","),
    caption,
    access_token: env.INSTAGRAM_ACCESS_TOKEN,
  });
  const carouselResp = await fetch(carouselUrl, { method: "POST", body: carouselBody });
  if (!carouselResp.ok) {
    throw new Error(`Carousel container failed: ${await carouselResp.text()}`);
  }
  const carousel = (await carouselResp.json()) as { id?: string };
  if (!carousel.id) {
    throw new Error("Instagram did not return carousel container id.");
  }

  // Step 3: publish the carousel
  return await publishContainerToInstagram(env, carousel.id);
}

async function publishContainerToInstagram(env: Env, creationId: string): Promise<string> {
  const publishUrl = `https://graph.facebook.com/v20.0/${env.INSTAGRAM_USER_ID}/media_publish`;
  const publishBody = new URLSearchParams({
    creation_id: creationId,
    access_token: env.INSTAGRAM_ACCESS_TOKEN,
  });
  const publishResponse = await fetch(publishUrl, { method: "POST", body: publishBody });
  if (!publishResponse.ok) {
    throw new Error(`Instagram publish failed: ${await publishResponse.text()}`);
  }
  const published = (await publishResponse.json()) as { id?: string };
  if (!published.id) {
    throw new Error("Instagram did not return published media id.");
  }
  return published.id;
}

function captionForInstagram(post: GeneratedPost): string {
  const tags = post.hashtags.join(" ");
  const sourcePublishers = post.sources
    .slice(0, 3)
    .map((source) => source.publisher || hostname(source.url))
    .filter(Boolean);
  const sources = sourcePublishers.length > 0 ? `\n\nSources: ${unique(sourcePublishers).join(", ")}` : "";
  const disclaimer =
    "\n\nEducational content only. Verify critical security decisions with official advisories.";
  return `${post.caption.trim()}${sources}${disclaimer}\n\n${tags}`.trim();
}

async function getPost(env: Env, postId: string): Promise<GeneratedPost | null> {
  return getPostByStorageKey(env, postKey(postId));
}

async function getPostByStorageKey(env: Env, key: string): Promise<GeneratedPost | null> {
  const raw = await env.POSTS_KV.get(key);
  if (!raw) return null;
  return JSON.parse(raw) as GeneratedPost;
}

async function putPost(env: Env, post: GeneratedPost): Promise<void> {
  await env.POSTS_KV.put(postKey(post.post_id), JSON.stringify(post));
}

async function sendTelegramMessage(env: Env, text: string): Promise<void> {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_ADMIN_CHAT_ID,
      text,
    }),
  });
}

async function answerCallback(env: Env, callbackQueryId: string, text: string): Promise<void> {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      callback_query_id: callbackQueryId,
      text,
      show_alert: false,
    }),
  });
}

function assertSharedSecret(request: Request, env: Env): Response | null {
  const provided = request.headers.get("X-CyberBriefs-Secret");
  if (!provided || provided !== env.WORKER_SHARED_SECRET) {
    return new Response("unauthorized", { status: 401 });
  }
  return null;
}

function validatePost(post: GeneratedPost): Response | null {
  if (!post.post_id || !post.headline || !post.caption) {
    return new Response("invalid post", { status: 400 });
  }
  return null;
}

function postKey(postId: string): string {
  return `post:${postId}`;
}

function indexKey(createdAt: string, postId: string): string {
  return `post-index:${createdAt}:${postId}`;
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function hostname(value: string): string {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}
