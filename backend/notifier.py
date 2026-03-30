"""Discord 通知モジュール

要約完了時にDiscord Webhookへ結果を送信する。
"""

import logging

import requests

from config import DISCORD_WEBHOOK_URL, GITHUB_PAGES_BASE_URL

logger = logging.getLogger(__name__)


def send_discord_notification(episode: dict, summary_text: str) -> bool:
    """DiscordのWebhookに要約完了通知を送信する（要約はリンクで提供）

    Args:
        episode: エピソード情報の辞書
        summary_text: 要約テキスト（現在は使用しないが互換性のため残す）

    Returns:
        送信成功時True, 失敗(または未設定)時False
    """
    if not DISCORD_WEBHOOK_URL:
        logger.debug("Discord Webhook URLが未設定のため通知をスキップ")
        return False

    podcast_title = episode.get("podcast_title", "Unknown Podcast")
    episode_title = episode.get("episode_title", "Unknown Episode")
    episode_id = episode.get("id")

    summary_url = f"{GITHUB_PAGES_BASE_URL}/{episode_id}.html"

    payload = {
        "content": (
            f"🎉 **要約が完了しました！**\n"
            f"**{podcast_title}**\n"
            f"_{episode_title}_\n\n"
            f"📖 [**要約を GitHub で読む**]({summary_url})"
        )
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL, json=payload, timeout=10,
        )
        response.raise_for_status()
        logger.info("📣 Discordへリンク付き通知を送信しました: %s", episode_title)
        return True
    except Exception as e:
        logger.error("❌ Discord通知の送信に失敗しました: %s", e)
        return False
