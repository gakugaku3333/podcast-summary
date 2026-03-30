"""Whisper 文字起こしモジュール

mlx-whisper を使用してApple Silicon GPUで高速に音声をテキストに変換する。
サブプロセスで実行し、完了後にメモリを自動で完全解放する。
"""

import logging
import multiprocessing as mp
from pathlib import Path

from config import WHISPER_LANGUAGE

logger = logging.getLogger(__name__)

# mlx-whisper で使用するモデル (Hugging Face Hub から自動ダウンロード)
MLX_MODEL = "mlx-community/whisper-medium-mlx"


def _transcribe_worker(
    audio_path_str: str, model: str, language: str, result_queue: mp.Queue
) -> None:
    """サブプロセス内で文字起こしを実行（メモリ隔離用）

    このワーカーはサブプロセスで実行されるため、
    プロセス終了時にMLXモデルのメモリが自動的に解放される。
    """
    try:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio_path_str,
            path_or_hf_repo=model,
            language=language,
            verbose=False,
        )

        text = result.get("text", "").strip()
        segments_count = len(result.get("segments", []))
        result_queue.put({
            "text": text,
            "segments_count": segments_count,
            "error": None,
        })
    except Exception as e:
        result_queue.put({
            "text": None,
            "segments_count": 0,
            "error": str(e),
        })


def transcribe_audio(audio_path: Path) -> str | None:
    """音声ファイルを文字起こし

    サブプロセスで mlx-whisper を実行し、完了後にプロセスごとメモリを解放する。
    これにより、メインサーバープロセスのメモリ使用量を最小限に保つ。

    Args:
        audio_path: 音声ファイルのパス

    Returns:
        文字起こしテキスト、失敗時はNone
    """
    if not audio_path.exists():
        logger.error("音声ファイルが存在しません: %s", audio_path)
        return None

    try:
        logger.info("文字起こし開始 (mlx-whisper, サブプロセス): %s", audio_path.name)

        result_queue = mp.Queue()
        process = mp.Process(
            target=_transcribe_worker,
            args=(str(audio_path), MLX_MODEL, WHISPER_LANGUAGE, result_queue),
        )
        process.start()
        process.join()  # 完了まで待機

        # プロセスの終了状態を確認
        if process.exitcode != 0:
            logger.error(
                "文字起こしサブプロセスが異常終了しました (exit code: %d)",
                process.exitcode,
            )
            return None

        if result_queue.empty():
            logger.error("文字起こしサブプロセスから結果を取得できませんでした")
            return None

        result = result_queue.get_nowait()

        # Queue を明示的に閉じる
        result_queue.close()
        result_queue.join_thread()

        if result["error"]:
            logger.error("文字起こしエラー: %s — %s", audio_path.name, result["error"])
            return None

        text = result["text"]
        if not text:
            logger.warning("文字起こし結果が空です: %s", audio_path.name)
            return None

        logger.info(
            "文字起こし完了: %s — %d文字, %dセグメント",
            audio_path.name,
            len(text),
            result["segments_count"],
        )
        logger.info("🧹 文字起こしサブプロセス終了 — MLXモデルのメモリを自動解放")

        return text

    except Exception as e:
        logger.error("文字起こしエラー: %s — %s", audio_path.name, e)
        return None
