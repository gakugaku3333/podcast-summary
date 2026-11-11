"""エピソード処理パイプライン

ユーザーがキャプチャしたエピソードの
ダウンロード→文字起こし→要約→通知→Git push を担う。
"""

import logging
import os
import subprocess
import threading

import database
import downloader
import notifier
import summarizer
import transcriber
import watcher
from config import PROJECT_ROOT, SUMMARIES_DIR

logger = logging.getLogger(__name__)

# --- 状態管理 ---
_processing_lock = threading.Lock()
_is_processing = False


def is_processing() -> bool:
    """パイプラインが処理中かどうか"""
    return _is_processing


# --- Git 連携 ---

def _git_push_summaries(episode_title: str) -> bool:
    """生成された要約を GitHub にプッシュする"""
    try:
        SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

        commands = [
            ["git", "add", "docs/summaries/"],
            ["git", "commit", "-m", f"Add summary: {episode_title}"],
            ["git", "push", "origin", "main"],
        ]

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        for cmd in commands:
            result = subprocess.run(
                cmd, cwd=PROJECT_ROOT, capture_output=True,
                text=True, check=False, env=env,
            )
            if result.returncode != 0:
                if "nothing to commit" in (result.stdout + result.stderr):
                    continue
                logger.error(
                    "Git error (%s): %s",
                    " ".join(cmd),
                    (result.stderr or result.stdout).strip(),
                )
                if cmd[1] == "push":
                    return False

        logger.info("🚀 GitHub へのプッシュが完了しました: %s", episode_title)
        return True
    except Exception as e:
        logger.error("❌ Git push エラー: %s", e)
        return False


# --- エピソード処理 ---

def _process_single_episode(episode: dict) -> None:
    """1つのエピソードを処理（ダウンロード→文字起こし→要約）"""
    ep_id = episode["id"]
    label = f"[{episode['podcast_title']}] {episode['episode_title']}"

    try:
        # Step 1: 音声ダウンロード
        logger.info("📥 音声取得中: %s", label)
        database.update_episode_status(ep_id, "downloading")

        audio_path = downloader.download_episode_audio(
            episode_id=ep_id,
            audio_url=episode.get("audio_url"),
            feed_url=episode.get("feed_url"),
            episode_title=episode["episode_title"],
        )
        if audio_path is None:
            database.update_episode_status(ep_id, "error")
            return

        # Step 2: 文字起こし
        logger.info("🎤 文字起こし中: %s", label)
        database.update_episode_status(ep_id, "transcribing")

        transcript = transcriber.transcribe_audio(audio_path)
        if transcript is None:
            database.update_episode_status(ep_id, "error")
            return

        database.update_episode_status(
            ep_id, "transcribing", transcript=transcript
        )

        # Step 3: 要約生成
        logger.info("✨ 要約生成中: %s", label)
        database.update_episode_status(ep_id, "summarizing")

        summary_text = summarizer.summarize_transcript(
            transcript=transcript,
            podcast_title=episode["podcast_title"],
            episode_title=episode["episode_title"],
        )
        if summary_text is None:
            database.update_episode_status(ep_id, "error", transcript=transcript)
            return

        # 完了
        database.update_episode_status(
            ep_id, "done", transcript=transcript, summary=summary_text
        )

        # HTML要約ファイルを保存 (GitHub Pages用)
        try:
            SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
            summary_file = SUMMARIES_DIR / f"{ep_id}.html"
            summary_file.write_text(summary_text, encoding="utf-8")
            logger.info("📄 要約ファイルを保存しました: %s", summary_file.name)
            _git_push_summaries(episode["episode_title"])
        except Exception as e:
            logger.error("❌ 要約ファイルの保存/プッシュに失敗: %s", e)

        logger.info("✅ 処理完了: %s", label)

        # Discord通知
        notifier.send_discord_notification(episode, summary_text)

        # 音声ファイルを削除（ディスク節約）
        try:
            audio_path.unlink()
            logger.info("🗑️ 音声ファイル削除: %s", audio_path.name)
        except Exception:
            pass

    except Exception as e:
        logger.error("❌ 処理エラー: %s — %s", label, e)
        database.update_episode_status(ep_id, "error")


# --- パイプライン実行 ---

def run_pipeline() -> int:
    """未処理（pending）のエピソードを順に処理する

    Returns:
        処理したエピソード数
    """
    global _is_processing

    if _is_processing:
        logger.debug("処理中のためスキップ")
        return 0

    with _processing_lock:
        _is_processing = True
        try:
            pending = database.get_pending_episodes()
            if not pending:
                return 0

            logger.info("📋 %d 件のエピソードを処理します", len(pending))
            for episode in pending:
                _process_single_episode(episode)

            return len(pending)
        finally:
            _is_processing = False


def trigger_async() -> bool:
    """パイプラインの非同期実行をトリガーする

    Returns:
        True: 処理を開始した, False: 既に処理中
    """
    if _is_processing:
        return False
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return True


# --- オンデマンドキャプチャ ---

def capture_and_process(apple_episode_id: int | None = None) -> dict | None:
    """エピソード1件をキャプチャして非同期処理を開始する

    Args:
        apple_episode_id: 対象のApple エピソードID。None なら直近再生中の回。

    Returns:
        キャプチャしたエピソード情報（見つからなければ None）
    """
    captured = watcher.capture_episode(apple_episode_id)
    if captured is None:
        return None

    # 既に処理済み（done）の回は再処理しない
    if captured.get("db_status") == "pending":
        trigger_async()

    return captured
