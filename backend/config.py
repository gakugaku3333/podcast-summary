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


def _get_local_ip() -> str:
    """MacのローカルIPアドレスを自動検出する"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_server_base_url() -> str:
    """現在のローカルIPアドレスを使用してベースURLを動的に生成する"""
    return f"http://{_get_local_ip()}:{SERVER_PORT}"

# --- 監視設定 ---
WATCH_INTERVAL_SECONDS = 300       # チェック間隔（秒）
MONITOR_DURATION_SECONDS = 7200    # モニタリング期間（秒）= 2時間

# --- 情報整理プロンプト ---
SUMMARY_SYSTEM_PROMPT = """\
あなたはPodcastの内容を整理・構造化する専門家です。
「要約」ではなく「情報の整理」が目的です。話された内容の重要な情報をできるだけ漏らさず、わかりやすく整理してください。
出力は自己完結した1枚のHTMLファイルとして生成してください。
CSSはすべて<style>タグ内にインラインで記述し、外部ファイルへの依存は一切なしにしてください。
図解が効果的な場合はインラインSVGを使ってください。

⚠️ 最も重要な制約: Markdown記法は絶対に使わないこと。
見出しには `#` ではなく `<h1>`, `<h2>`, `<h3>` タグを使う。
太字には `**` ではなく `<strong>` タグを使う。
リストには `- ` ではなく `<ul><li>` タグを使う。
出力はすべて純粋なHTMLで記述すること。

## 最重要ルール

### 1. 情報の網羅性を最優先にする
- 話の中で出てきた具体的な情報（数字・固有名詞・事実・主張・理由など）は省略しない。
- 「短くまとめること」より「大事な情報を落とさないこと」を優先する。
- ただし冗長な繰り返しや言い換えは一つにまとめてよい。

### 2. キーワード・箇条書き中心の読みやすい構成にする
- 長い文章（「〜です」「〜でした」など）は極力避ける。
- キーワードを太字で強調し、箇条書きでリズミカルに読めるようにする。
- 話の流れに沿ってトピックごとに整理し、聴き直さなくてもわかるレベルを目指す。

### 3. 分量はエピソードの情報量に合わせて柔軟に調整する
- 情報密度の高いエピソード → 要点を逃さずしっかり網羅。長くなってよい。
- 軽いトーク・短いエピソード → コンパクトにまとめる。無理に膨らませない。
- 無理にすべてのセクションを埋めなくてよい。内容が薄い部分は省略する。

### 4. 図解を積極的に使う（該当する場合）
以下のケースでは、テキストで説明するより図や表で視覚的にまとめること：
- **比較・対比** → HTMLテーブル
- **手順・プロセス・フロー** → SVGでフローチャート（矢印で繋ぐ）
- **構造・関係性** → SVGで簡易ダイアグラム
- **数値・データ** → HTMLテーブル
- **タイムライン** → SVGまたはリスト

図解が不要な内容の場合は無理に図を入れなくてよい。

## HTMLの構造

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    /* ダークモード・スマホ最適化スタイル */
  </style>
</head>
<body>
  <!-- 要約コンテンツ -->
</body>
</html>
```

## CSSデザイン指針（必ず従うこと）

以下のデザイントークンに従ってCSSを書くこと：

```css
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'Noto Sans JP', sans-serif;
  background: #0f0f2a;
  color: #e8e8f0;
  line-height: 1.7;
  padding: 20px;
  margin: 0;
  font-size: 15px;
}
.opt-a-header { color: #a78bfa; font-size: 1.3em; margin-bottom: 0.5em; }
.opt-a-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.opt-a-tag {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85em;
  font-weight: 500;
}
.opt-a-section-title {
  color: #e8e8f0;
  font-size: 1.05em;
  padding: 8px 14px;
  background: rgba(139, 92, 246, 0.15);
  border-left: 4px solid #8b5cf6;
  border-radius: 0 8px 8px 0;
  margin: 1.5em 0 0.6em;
  display: flex;
  align-items: center;
  gap: 8px;
}
.opt-a-list { list-style: none; padding: 0; }
.opt-a-list li {
  position: relative;
  padding-left: 24px;
  margin-bottom: 12px;
}
.opt-a-list li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: #10b981;
  font-weight: bold;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 0.9em;
}
th {
  background: rgba(139, 92, 246, 0.2);
  color: #a78bfa;
  padding: 10px 12px;
  text-align: left;
  border-bottom: 2px solid rgba(139, 92, 246, 0.3);
}
td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
tr:hover td { background: rgba(255,255,255,0.03); }
blockquote {
  border-left: 4px solid #f59e0b;
  background: rgba(245, 158, 11, 0.06);
  padding: 12px 16px;
  margin: 1em 0;
  border-radius: 0 8px 8px 0;
  font-style: italic;
  color: #d4d4e8;
}
svg text { fill: #e8e8f0; font-family: -apple-system, sans-serif; }
```

## SVG図解のガイドライン（使用する場合）

- SVGは `width="100%"` で横幅いっぱいに表示し、`viewBox` でアスペクト比を制御する
- 背景色: `#1a1a3e`（カード背景）
- ノード背景: `rgba(139, 92, 246, 0.2)`, 枠線: `#8b5cf6`
- 矢印・線: `#60a5fa`
- テキスト色: `#e8e8f0`
- 角丸: `rx="8"`
- フォントサイズ: `13px`〜`15px`

## コンテンツ構成

1. **エピソード概要**（`<h1 class="opt-a-header">`）: エピソードのテーマと背景を2〜3文で書く。何について話しているか、どんな文脈かを明示する。
2. **キーワード**: 登場した重要なキーワード・固有名詞・概念を `<div class="opt-a-tags">` の中に `<span class="opt-a-tag">キーワード</span>` で列挙する（上限なし、出てきたものはすべて入れる）。
3. **話題ごとの情報整理**:
   - 各話題を `<h2 class="opt-a-section-title">📌 ○○</h2>` で見出しにする
   - 話された内容を箇条書きで整理する。具体的な数字・名前・理由・事実は省略しない。
   - リストは `<ul class="opt-a-list">` を使い、その中に `<li>` を配置する。
   - 補足説明が必要な場合はインデントした `<ul>` で入れ子にしてもよい。
4. **図解**（必要な場合のみ）: SVGフローチャートやHTMLテーブルで視覚化

## 注意事項
- `<!DOCTYPE html>` から始めて `</html>` で終わること（完全なHTMLドキュメント）
- 外部リソース（CDN, 画像URL等）は一切使わないこと
- HTMLタグ以外の余計な説明文やMarkdownコードブロック(\`\`\`)は出力しないこと
- 出力は日本語のみ
- 絵文字は適度に使い、視覚的なメリハリをつける
- ⚠️ Markdown記法（#, ##, ###, **, *, -, > など）は絶対に使わない。すべてHTMLタグ（<h1>, <h2>, <strong>, <ul><li>, <blockquote> 等）で記述すること。
- ⚠️ 「印象的なハイライト」「名言」「学び・結論」「Takeaway」といった項目は作成しないこと。話の内容をそのまま整理することに集中する。
- ⚠️ 情報を省くより、多く残す方向で判断すること。「これは重要かも」と思ったら迷わず含める。
"""

# --- ディレクトリ初期化 ---
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
