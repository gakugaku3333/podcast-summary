"""FastAPI メインサーバー

エピソード処理パイプラインの統合と、
フロントエンド配信・APIエンドポイントを提供する。
"""

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import database
import watcher
import downloader
import transcriber
import summarizer
import notifier
import subprocess
from config import (
    MONITOR_DURATION_SECONDS,
    SERVER_HOST,
    SERVER_PORT,
    WATCH_INTERVAL_SECONDS,
    SUMMARIES_DIR,
    PROJECT_ROOT,
)

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- 監視・処理状態管理 ---
_processing_lock = threading.Lock()
_is_processing = False
_monitor_end_time = 0.0  # UNIX timestamp


def git_push_summaries(episode_title: str) -> bool:
    """生成された要約を GitHub にプッシュする"""
    try:
        # ディレクトリを確実に作成
        SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
        
        # Git 操作
        commands = [
            ["git", "add", "docs/summaries/"],
            ["git", "commit", "-m", f"Add summary: {episode_title}"],
            ["git", "push", "origin", "main"]
        ]
        
        for cmd in commands:
            # 認証待ちでブロックされないように環境変数を設定
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            if result.returncode != 0:
                # 変更がない場合は commit が失敗するが、それは無視してよい
                if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                    continue
                logger.error("Git error (%s): %s", " ".join(cmd), (result.stderr or result.stdout).strip())
                if "push" in cmd[1]: # push失敗は致命的
                    return False
        
        logger.info("🚀 GitHub へのプッシュが完了しました: %s", episode_title)
        return True
    except Exception as e:
        logger.error("❌ Git push エラー: %s", e)
        return False


def process_single_episode(episode: dict) -> None:
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
        
        # HTMLをファイルとして保存 (GitHub Pages用)
        try:
            SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
            summary_file = SUMMARIES_DIR / f"{ep_id}.html"
            summary_file.write_text(summary_text, encoding="utf-8")
            logger.info("📄 要約ファイルを保存しました: %s", summary_file.name)
            
            # GitHubにプッシュ
            git_push_summaries(episode["episode_title"])
        except Exception as e:
            logger.error("❌ 要約ファイルの保存/プッシュに失敗: %s", e)

        logger.info("✅ 処理完了: %s", label)

        # Discordに通知を送信
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


def run_pipeline() -> int:
    """処理パイプラインを実行

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
            # 新しいエピソードを検出・登録
            watcher.check_and_register_new_episodes()

            # 未処理エピソードを処理
            pending = database.get_pending_episodes()
            if not pending:
                return 0

            logger.info("📋 %d 件のエピソードを処理します", len(pending))
            for episode in pending:
                process_single_episode(episode)

            return len(pending)
        finally:
            _is_processing = False


def monitor_loop():
    """時限式で定期的にパイプラインを実行するループ"""
    global _monitor_end_time
    
    logger.info("🕒 時限式モニタリングループを開始しました")
    
    while time.time() < _monitor_end_time:
        try:
            run_pipeline()
        except Exception as e:
            logger.error("パイプラインエラー: %s", e)
            
        # 残り時間が監視間隔に満たない場合は、残り時間だけ待つ
        remaining = _monitor_end_time - time.time()
        if remaining <= 0:
            break
            
        sleep_time = min(WATCH_INTERVAL_SECONDS, remaining)
        logger.info("💤 次のチェックまで %d 秒待機 (監視残り: %d分)", sleep_time, int(remaining/60))
        time.sleep(sleep_time)

    logger.info("🛑 モニタリング期間（2時間）が終了しました。待機状態に戻ります")
    _monitor_end_time = 0.0


# --- FastAPI アプリ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """サーバー起動・終了時の処理"""
    logger.info("🚀 サーバーが待機状態で起動しました（モニタリング停止中）")
    yield
    logger.info("👋 サーバー停止")


app = FastAPI(
    title="Podcast 自動解説",
    description="Podcastを自動で文字起こし・要約するアプリ",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 静的ファイル配信 ---
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# --- API エンドポイント ---
@app.get("/api/episodes")
async def list_episodes(limit: int = 50, offset: int = 0):
    """エピソード一覧を取得"""
    episodes = database.get_all_episodes(limit=limit, offset=offset)
    counts = database.get_episode_count()
    return {"episodes": episodes, "counts": counts}


@app.get("/api/episodes/{episode_id}")
async def get_episode(episode_id: int):
    """エピソード詳細を取得"""
    episode = database.get_episode_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="エピソードが見つかりません")
    return episode


@app.get("/api/episodes/{episode_id}/summary")
async def get_episode_summary_html(episode_id: int):
    """エピソードのHTML要約をそのまま返す（Safariで直接表示用）"""
    from fastapi.responses import HTMLResponse

    episode = database.get_episode_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="エピソードが見つかりません")

    summary = episode.get("summary")
    if not summary:
        raise HTTPException(status_code=404, detail="要約がまだありません")

    # HTMLかどうかを判定
    if summary.strip().startswith("<!DOCTYPE") or summary.strip().startswith("<html"):
        return HTMLResponse(content=summary)
    else:
        # 旧Markdown要約の場合は簡易的にHTMLでラップして返す
        escaped = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body {{ font-family: -apple-system, sans-serif; background: #0f0f2a; color: #e8e8f0; padding: 20px; line-height: 1.7; white-space: pre-wrap; }}</style>
</head><body>{escaped}</body></html>"""
        return HTMLResponse(content=html)


@app.post("/api/scan")
async def trigger_scan():
    """手動でスキャンをトリガー"""
    new_episodes = watcher.check_and_register_new_episodes()
    return {
        "message": f"{len(new_episodes)} 件の新しいエピソードを検出",
        "new_episodes": len(new_episodes),
    }


@app.post("/api/process")
async def trigger_process():
    """手動で処理パイプラインを1回だけトリガー（単発）"""
    if _is_processing:
        return {"message": "処理中です。しばらくお待ちください。", "processing": True}

    # バックグラウンドで単発処理を開始
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return {"message": "1回限りの処理を開始しました", "processing": True}


@app.post("/api/monitor")
async def start_monitoring():
    """時限モニタリングを開始する（iPhone自動化トリガー用）"""
    global _monitor_end_time
    
    is_already_running = _monitor_end_time > time.time()
    
    # 終了時刻を現在から2時間後に設定・延長
    _monitor_end_time = time.time() + MONITOR_DURATION_SECONDS
    
    if not is_already_running:
        # 監視スレッドが停止していた場合は新しく起動
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        msg = "2時間のモニタリングを開始しました"
    else:
        msg = "モニタリングの残り時間を2時間に延長しました"
        
    return {"message": msg, "monitor_active": True, "duration_minutes": MONITOR_DURATION_SECONDS // 60}


@app.get("/api/status")
async def get_status():
    """システムステータスを取得"""
    counts = database.get_episode_count()
    is_monitoring = _monitor_end_time > time.time()
    sub_status = "監視中" if is_monitoring else "待機中"
    
    # /api/status はフロントエンドのUIでも使われるので
    # 監視状態をわかりやすく返す
    return {
        "processing": _is_processing,
        "is_monitoring": is_monitoring,
        "status_text": "処理中" if _is_processing else sub_status,
        "counts": counts,
        "watch_interval": WATCH_INTERVAL_SECONDS,
    }


# --- フロントエンド配信 ---
# html=True により、/ にアクセスすると自動的に index.html を探し、
# それ以外のパス（/app.js, /style.css等）も正しく配信します。
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# --- エントリーポイント ---
if __name__ == "__main__":
    import uvicorn

    logger.info("🎧 Podcast 自動解説サーバーを起動します")
    logger.info("📱 iPhone からは http://<MacのIPアドレス>:%d でアクセス", SERVER_PORT)

    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )
