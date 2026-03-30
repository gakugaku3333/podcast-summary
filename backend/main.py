"""FastAPI メインサーバー

フロントエンド配信・APIエンドポイントを提供する。
パイプラインロジックは pipeline モジュールに委譲。
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import database
import pipeline
from config import (
    MONITOR_DURATION_SECONDS,
    SERVER_HOST,
    SERVER_PORT,
    WATCH_INTERVAL_SECONDS,
)

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- FastAPI アプリ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """サーバー起動・終了時の処理"""
    cleaned = database.cleanup_old_episode_data(days=30)
    if cleaned:
        logger.info("🗑️ %d 件の古いデータをクリーンアップしました（30日経過分）", cleaned)
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
    episode = database.get_episode_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="エピソードが見つかりません")

    summary = episode.get("summary")
    if not summary:
        raise HTTPException(status_code=404, detail="要約がまだありません")

    # HTMLかどうかを判定
    if summary.strip().startswith("<!DOCTYPE") or summary.strip().startswith("<html"):
        return HTMLResponse(content=summary)

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
    import watcher
    new_episodes = watcher.check_and_register_new_episodes()
    return {
        "message": f"{len(new_episodes)} 件の新しいエピソードを検出",
        "new_episodes": len(new_episodes),
    }


@app.post("/api/process")
async def trigger_process():
    """手動で処理パイプラインを1回だけトリガー（単発）"""
    if not pipeline.trigger_async():
        return {"message": "処理中です。しばらくお待ちください。", "processing": True}
    return {"message": "1回限りの処理を開始しました", "processing": True}


@app.post("/api/monitor")
async def start_monitoring():
    """時限モニタリングを開始する（iPhone自動化トリガー用）"""
    newly_started = pipeline.start_monitor()
    msg = "2時間のモニタリングを開始しました" if newly_started else "モニタリングの残り時間を2時間に延長しました"
    return {
        "message": msg,
        "monitor_active": True,
        "duration_minutes": MONITOR_DURATION_SECONDS // 60,
    }


@app.get("/api/status")
async def get_status():
    """システムステータスを取得"""
    counts = database.get_episode_count()
    monitoring = pipeline.is_monitoring()
    processing = pipeline.is_processing()
    sub_status = "監視中" if monitoring else "待機中"

    return {
        "processing": processing,
        "is_monitoring": monitoring,
        "status_text": "処理中" if processing else sub_status,
        "counts": counts,
        "watch_interval": WATCH_INTERVAL_SECONDS,
    }


# --- フロントエンド配信 ---
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# --- エントリーポイント ---
if __name__ == "__main__":
    import uvicorn

    logger.info("🎧 Podcast 自動解説サーバーを起動します")

    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )
