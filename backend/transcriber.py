"""Whisper 文字起こしモジュール

mlx-whisper を使用してApple Silicon GPUで高速に音声をテキストに変換する。
"""

import logging
from pathlib import Path

import mlx_whisper

from config import WHISPER_LANGUAGE

logger = logging.getLogger(__name__)

# mlx-whisper で使用するモデル (Hugging Face Hub から自動ダウンロード)
MLX_MODEL = "mlx-community/whisper-medium-mlx"


def transcribe_audio(audio_path: Path) -> str | None:
    """音声ファイルを文字起こし

    Args:
        audio_path: 音声ファイルのパス

    Returns:
        文字起こしテキスト、失敗時はNone
    """
    if not audio_path.exists():
        logger.error("音声ファイルが存在しません: %s", audio_path)
        return None

    try:
        logger.info("文字起こし開始 (mlx-whisper): %s", audio_path.name)

        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=MLX_MODEL,
            language=WHISPER_LANGUAGE,
            verbose=False,
        )

        text = result.get("text", "").strip()
        if not text:
            logger.warning("文字起こし結果が空です: %s", audio_path.name)
            return None

        segments = result.get("segments", [])
        logger.info(
            "文字起こし完了: %s — %d文字, %dセグメント",
            audio_path.name,
            len(text),
            len(segments),
        )

        return text

    except Exception as e:
        logger.error("文字起こしエラー: %s — %s", audio_path.name, e)
        return None
