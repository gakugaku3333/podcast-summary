"""設定管理モジュール"""

import os
from pathlib import Path

# --- パス設定 ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
APP_DB_PATH = DATA_DIR / "app.db"
DOCS_DIR = PROJECT_ROOT / "docs"
SUMMARIES_DIR = DOCS_DIR / "summaries"

# GitHub Pages 設定
GITHUB_USER = "gakugaku3333"
GITHUB_REPO = "podcast-summary"
GITHUB_PAGES_BASE_URL = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/summaries"

# Apple Podcasts DB
APPLE_PODCASTS_DB = Path.home() / (
    "Library/Group Containers/"
    "243LU875E5.groups.com.apple.podcasts/"
    "Documents/MTLibrary.sqlite"
)

# --- Whisper 設定 ---
WHISPER_LANGUAGE = "ja"

# --- API 設定 ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3-flash-preview"

# --- 通知設定 ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# --- サーバー設定 ---
SERVER_HOST = "::"
SERVER_PORT = 8000

# --- 監視設定 ---
WATCH_INTERVAL_SECONDS = 300       # チェック間隔（秒）
MONITOR_DURATION_SECONDS = 7200    # モニタリング期間（秒）= 2時間

# --- ディレクトリ初期化 ---
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
