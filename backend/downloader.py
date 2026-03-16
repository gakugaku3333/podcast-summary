"""音声ダウンロードモジュール

RSSフィードから音声ファイルをダウンロードする。
ローカルキャッシュが利用可能な場合はそれを使用する。
"""

import logging
import shutil
from pathlib import Path
from urllib.parse import urlparse, unquote

import feedparser
import requests

from config import AUDIO_DIR

logger = logging.getLogger(__name__)

# ダウンロードタイムアウト（秒）
DOWNLOAD_TIMEOUT = 600
# チャンクサイズ（バイト）
CHUNK_SIZE = 8192


def _sanitize_filename(name: str, max_length: int = 80) -> str:
    """ファイル名として安全な文字列に変換"""
    # 危険な文字を除去
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    return safe[:max_length]


def find_audio_url_from_feed(feed_url: str, episode_title: str) -> str | None:
    """RSSフィードからエピソードの音声URLを探す

    Args:
        feed_url: PodcastのRSSフィードURL
        episode_title: エピソードタイトル

    Returns:
        音声ファイルのURL、見つからなければNone
    """
    if not feed_url:
        return None

    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if entry.get("title", "").strip() == episode_title.strip():
                # enclosure（添付ファイル）から音声URLを取得
                for link in entry.get("links", []):
                    if link.get("type", "").startswith("audio/"):
                        return link["href"]
                # enclosures属性もチェック
                for enc in entry.get("enclosures", []):
                    if enc.get("type", "").startswith("audio/"):
                        return enc["href"]
        logger.warning(
            "RSSフィードにエピソードが見つかりません: %s", episode_title
        )
    except Exception as e:
        logger.error("RSSフィード解析エラー: %s — %s", feed_url, e)

    return None


def _copy_local_cache(cache_path: str, dest: Path) -> bool:
    """ローカルキャッシュからコピー"""
    try:
        src = Path(unquote(urlparse(cache_path).path))
        if src.exists():
            shutil.copy2(src, dest)
            logger.info("ローカルキャッシュからコピー: %s", src.name)
            return True
        else:
            logger.warning("ローカルキャッシュが消失: %s", src)
    except Exception as e:
        logger.error("キャッシュコピーエラー: %s", e)
    return False


def _download_from_url(url: str, dest: Path) -> bool:
    """URLから音声ファイルをダウンロード"""
    try:
        logger.info("ダウンロード開始: %s", url)
        resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
                downloaded += len(chunk)

        logger.info(
            "ダウンロード完了: %s (%.1f MB)",
            dest.name,
            downloaded / 1024 / 1024,
        )
        return True
    except Exception as e:
        logger.error("ダウンロードエラー: %s — %s", url, e)
        if dest.exists():
            dest.unlink()
        return False


def download_episode_audio(
    episode_id: int,
    audio_url: str | None,
    feed_url: str | None,
    episode_title: str,
) -> Path | None:
    """エピソードの音声ファイルを取得

    優先順位:
    1. ローカルキャッシュ（Apple Podcastsが保存したMP3）
    2. 既知の音声URL
    3. RSSフィードから探索

    Args:
        episode_id: エピソードID
        audio_url: 既知の音声URL（ローカルまたはリモート）
        feed_url: RSSフィードURL
        episode_title: エピソードタイトル

    Returns:
        ダウンロードした音声ファイルのPath、失敗時はNone
    """
    safe_name = _sanitize_filename(f"ep_{episode_id}_{episode_title}")
    dest = AUDIO_DIR / f"{safe_name}.mp3"

    # 既にダウンロード済みならスキップ
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("既にダウンロード済み: %s", dest.name)
        return dest

    # 1. ローカルキャッシュを試行
    if audio_url and audio_url.startswith("file://"):
        if _copy_local_cache(audio_url, dest):
            return dest

    # 2. リモートURLからダウンロード
    remote_url = audio_url if audio_url and not audio_url.startswith("file://") else None

    if not remote_url and feed_url:
        # 3. RSSフィードから探索
        remote_url = find_audio_url_from_feed(feed_url, episode_title)

    if remote_url:
        if _download_from_url(remote_url, dest):
            return dest

    logger.error(
        "音声ファイルを取得できません: [%d] %s", episode_id, episode_title
    )
    return None
