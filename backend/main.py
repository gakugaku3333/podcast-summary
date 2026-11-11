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
import watcher
from config import RECENT_HOURS, SERVER_HOST, SERVER_PORT

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


@app.get("/api/recent")
def list_recent_played(hours: int = RECENT_HOURS):
    """最近再生したエピソード一覧（キャプチャ候補）を取得

    Apple Podcasts DB を読むだけで、登録は行わない。
    """
    try:
        episodes = watcher.get_recent_episodes_with_status(since_hours=hours)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"episodes": episodes}


@app.post("/api/capture")
def capture_episode(payload: dict | None = None):
    """エピソード1件をキャプチャして処理を開始する

    - body なし（または apple_episode_id なし）: 直近に再生した回＝「今聴いている回」
    - body に apple_episode_id あり: その回

    iPhone ショートカットからは body なしの POST でワンタップ利用できる。
    """
    apple_episode_id = (payload or {}).get("apple_episode_id")

    captured = pipeline.capture_and_process(apple_episode_id)
    if captured is None:
        raise HTTPException(
            status_code=404,
            detail="対象のエピソードが見つかりません（最近再生した回がないか、同期待ちの可能性があります）",
        )

    status = captured.get("db_status")
    if status == "done":
        msg = f"「{captured['episode_title']}」は要約済みです"
    elif status == "pending":
        msg = f"「{captured['episode_title']}」の要約を開始しました"
    else:
        msg = f"「{captured['episode_title']}」は現在処理中です"

    return {
        "message": msg,
        "episode": {
            "id": captured["id"],
            "apple_episode_id": captured["apple_episode_id"],
            "podcast_title": captured["podcast_title"],
            "episode_title": captured["episode_title"],
            "status": status,
        },
    }


@app.post("/api/process")
async def trigger_process():
    """未処理（pending）エピソードの処理を手動でトリガー"""
    if not pipeline.trigger_async():
        return {"message": "処理中です。しばらくお待ちください。", "processing": True}
    return {"message": "処理を開始しました", "processing": True}


@app.get("/api/status")
async def get_status():
    """システムステータスを取得"""
    counts = database.get_episode_count()
    processing = pipeline.is_processing()

    return {
        "processing": processing,
        "status_text": "処理中" if processing else "待機中",
        "counts": counts,
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
