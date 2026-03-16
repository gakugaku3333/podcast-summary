"""Apple Podcasts DB 監視モジュール

macOSのApple Podcasts SQLiteデータベースを監視し、
新しく再生されたエピソードを検出する。
"""

import logging
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from config import APPLE_PODCASTS_DB
import database

logger = logging.getLogger(__name__)

# Apple Podcasts DBの日付は Core Data epoch (2001-01-01) ベース
CORE_DATA_EPOCH_OFFSET = 978307200  # 2001-01-01 からの秒数


def _convert_core_data_timestamp(timestamp: float | None) -> str | None:
    """Core Data タイムスタンプをISO形式文字列に変換"""
    if timestamp is None:
        return None
    unix_ts = timestamp + CORE_DATA_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M:%S")


def _copy_db_to_temp() -> Path:
    """Apple Podcasts DBを一時ディレクトリにコピーしてロック・TCC問題を回避する

    Returns:
        コピー先のDBファイルパス
    """
    temp_dir = Path(tempfile.gettempdir()) / "podcast_summary_tmp"
    temp_dir.mkdir(exist_ok=True)

    temp_db = temp_dir / "MTLibrary.sqlite"
    subprocess.run(
        ["cp", "-p", str(APPLE_PODCASTS_DB), str(temp_db)], check=False
    )

    # WAL と SHM もコピーしないと最新の再生履歴が取れない
    for suffix in ("-wal", "-shm"):
        src = APPLE_PODCASTS_DB.with_name(f"MTLibrary.sqlite{suffix}")
        if src.exists():
            subprocess.run(
                ["cp", "-p", str(src), str(temp_dir / f"MTLibrary.sqlite{suffix}")],
                check=False,
            )

    return temp_db


def get_apple_podcasts_connection() -> sqlite3.Connection:
    """Apple Podcasts DBへの読み取り専用接続を取得（ロック・TCC回避版）"""
    if not APPLE_PODCASTS_DB.exists():
        raise FileNotFoundError(
            f"Apple Podcasts DB が見つかりません: {APPLE_PODCASTS_DB}"
        )

    temp_db = _copy_db_to_temp()
    conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_recently_played_episodes(
    since_hours: int = 24,
) -> list[dict]:
    """最近再生されたエピソードをApple Podcasts DBから取得

    Args:
        since_hours: 何時間前までのエピソードを取得するか

    Returns:
        再生済みエピソードのリスト
    """
    conn = get_apple_podcasts_connection()
    try:
        # since_hours 時間前のCore Dataタイムスタンプ
        cutoff = (
            datetime.now() - timedelta(hours=since_hours)
        ).timestamp() - CORE_DATA_EPOCH_OFFSET

        rows = conn.execute(
            """
            SELECT
                e.Z_PK as episode_id,
                e.ZTITLE as episode_title,
                e.ZPLAYSTATE as play_state,
                e.ZLASTDATEPLAYED as last_played,
                e.ZASSETURL as asset_url,
                e.ZDURATION as duration,
                e.ZENCLOSUREURL as enclosure_url,
                p.ZTITLE as podcast_title,
                p.ZFEEDURL as feed_url,
                p.ZAUTHOR as author
            FROM ZMTEPISODE e
            LEFT JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
            WHERE e.ZLASTDATEPLAYED IS NOT NULL
              AND e.ZLASTDATEPLAYED > ?
            ORDER BY e.ZLASTDATEPLAYED DESC
            """,
            (cutoff,),
        ).fetchall()

        return [
            {
                "apple_episode_id": row["episode_id"],
                "episode_title": row["episode_title"] or "不明なエピソード",
                "play_state": row["play_state"],
                "played_at": _convert_core_data_timestamp(row["last_played"]),
                "asset_url": row["asset_url"],
                "enclosure_url": row["enclosure_url"],
                "duration": row["duration"],
                "podcast_title": row["podcast_title"] or "不明なPodcast",
                "feed_url": row["feed_url"],
                "author": row["author"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def check_and_register_new_episodes() -> list[dict]:
    """新しく再生されたエピソードをチェックし、アプリDBに登録

    Returns:
        新しく登録されたエピソードのリスト
    """
    recently_played = fetch_recently_played_episodes(since_hours=48)
    new_episodes = []

    for ep in recently_played:
        # 音声URLの決定: ローカルキャッシュ > エンクロージャURL > RSSから取得
        audio_url = ep.get("asset_url") or ep.get("enclosure_url")

        inserted_id = database.insert_episode(
            apple_episode_id=ep["apple_episode_id"],
            podcast_title=ep["podcast_title"],
            episode_title=ep["episode_title"],
            feed_url=ep.get("feed_url"),
            audio_url=audio_url,
            duration=ep.get("duration"),
            played_at=ep["played_at"],
        )

        if inserted_id is not None:
            logger.info(
                "新しいエピソードを登録: [%s] %s",
                ep["podcast_title"],
                ep["episode_title"],
            )
            new_episodes.append({**ep, "id": inserted_id})

    if new_episodes:
        logger.info("%d 件の新しいエピソードを検出", len(new_episodes))
    else:
        logger.debug("新しいエピソードは見つかりません")

    return new_episodes
