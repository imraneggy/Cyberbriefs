from cyberbriefs.models import GeneratedPost


def test_caption_for_instagram_adds_hashtags_and_disclaimer() -> None:
    post = GeneratedPost(
        topic="Credential stuffing",
        slot="morning",
        headline="Credential Stuffing Explained",
        image_prompt="Create an infographic.",
        image_alt_text="Infographic about credential stuffing.",
        caption="Password reuse creates risk.",
        hashtags=["#CyberSecurity", "#Privacy"],
    )

    caption = post.caption_for_instagram()

    assert "Password reuse creates risk." in caption
    assert "Educational content only" in caption
    assert "#CyberSecurity #Privacy" in caption
