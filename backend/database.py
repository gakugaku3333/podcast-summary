"""アプリ内データベース管理モジュール

処理済みエピソードの状態を管理するSQLiteデータベース。
Apple Podcasts DBとは別に、このアプリ独自のDBを持つ。
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from config import APP_DB_PATH


def get_connection() -> sqlite3.Connection:
    """DB接続を取得"""
    conn = sqlite3.connect(str(APP_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """データベースを初期化（テーブル作成）"""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apple_episode_id INTEGER UNIQUE NOT NULL,
            podcast_title TEXT NOT NULL,
            episode_title TEXT NOT NULL,
            feed_url TEXT,
            audio_url TEXT,
            duration REAL,
            played_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            transcript TEXT,
            summary TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_episodes_status
            ON episodes(status);
        CREATE INDEX IF NOT EXISTS idx_episodes_played_at
            ON episodes(played_at DESC);
    """)
    conn.commit()
    conn.close()


def insert_episode(
    apple_episode_id: int,
    podcast_title: str,
    episode_title: str,
    feed_url: str | None,
    audio_url: str | None,
    duration: float | None,
    played_at: str,
) -> int | None:
    """新しいエピソードを追加（重複は無視）

    Returns:
        挿入された行のID、または重複時はNone
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO episodes
                (apple_episode_id, podcast_title, episode_title,
                 feed_url, audio_url, duration, played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (apple_episode_id, podcast_title, episode_title,
             feed_url, audio_url, duration, played_at),
        )
        conn.commit()
        return cursor.lastrowid if cursor.rowcount > 0 else None
    finally:
        conn.close()


def update_episode_status(episode_id: int, status: str, **fields) -> None:
    """エピソードのステータスと任意のフィールドを更新

    Args:
        episode_id: エピソードID
        status: 新しいステータス ('pending', 'downloading', 'transcribing',
                'summarizing', 'done', 'error')
        **fields: 追加で更新するフィールド (transcript, summary など)
    """
    conn = get_connection()
    try:
        sets = ["status = ?", "updated_at = datetime('now', 'localtime')"]
        values: list = [status]

        for key, value in fields.items():
            sets.append(f"{key} = ?")
            values.append(value)

        values.append(episode_id)
        conn.execute(
            f"UPDATE episodes SET {', '.join(sets)} WHERE id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_episodes() -> list[dict]:
    """未処理のエピソードを取得"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM episodes WHERE status = 'pending' ORDER BY played_at ASC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_episodes(limit: int = 50, offset: int = 0) -> list[dict]:
    """全エピソードを取得（最新順）"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY played_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_episode_by_id(episode_id: int) -> dict | None:
    """IDでエピソードを取得"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_episode_count() -> dict:
    """ステータス別エピソード数を取得"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM episodes GROUP BY status"
        ).fetchall()
        result = {row["status"]: row["count"] for row in rows}
        result["total"] = sum(result.values())
        return result
    finally:
        conn.close()


# モジュール読み込み時にDB初期化
init_db()
