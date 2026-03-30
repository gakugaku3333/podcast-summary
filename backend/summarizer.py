"""Gemini API 要約モジュール

Gemini Flash を使用してPodcastの文字起こしテキストを
構造化されたHTML形式で整理する。
"""

import logging

from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from prompt import SUMMARY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Gemini クライアント（遅延初期化）
_client = None


def _get_client():
    """Geminiクライアントを取得（遅延初期化）"""
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY が設定されていません。"
                "環境変数 GEMINI_API_KEY を設定してください。"
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini クライアント初期化完了")
    return _client


def summarize_transcript(
    transcript: str,
    podcast_title: str,
    episode_title: str,
) -> str | None:
    """文字起こしテキストを要約

    Args:
        transcript: 文字起こしテキスト
        podcast_title: Podcast名
        episode_title: エピソードタイトル

    Returns:
        要約テキスト（HTML形式）、失敗時はNone
    """
    if not transcript or not transcript.strip():
        logger.warning("空のテキストが渡されました")
        return None

    try:
        client = _get_client()

        user_prompt = f"""以下のPodcastエピソードの内容を要約してください。

**Podcast名**: {podcast_title}
**エピソード名**: {episode_title}

---

{transcript}
"""

        logger.info(
            "要約生成開始: [%s] %s (%d文字)",
            podcast_title,
            episode_title,
            len(transcript),
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config={
                "system_instruction": SUMMARY_SYSTEM_PROMPT,
                "temperature": 0.3,
                "max_output_tokens": 8192,
            },
        )

        summary = response.text.strip()

        if not summary:
            logger.warning("要約結果が空です")
            return None

        logger.info(
            "要約生成完了: [%s] %s — %d文字",
            podcast_title,
            episode_title,
            len(summary),
        )

        return summary

    except Exception as e:
        logger.error("要約生成エラー: %s", e)
        return None
