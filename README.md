# 🎧 Podcast 自動解説

Apple Podcasts で再生したエピソードを**自動で文字起こし・要約**し、Discord に通知するアプリ。

## 機能

- 📡 Apple Podcasts の再生履歴を自動検出（SQLite 監視）
- 🎤 mlx-whisper (medium) による Apple Silicon GPU 対応の高速ローカル文字起こし
- ✨ Gemini Flash による日本語要約生成（**AI出力時点で構造化された美しい見出し・タグ・SVG図解付き**の自己完結HTML）
- 📱 iPhone から閲覧できる PWA ＋ Safari直接表示（モバイルファースト・ダークモード）
- 🔔 要約完了時に Discord へ自動通知（**PWA要約ページへの動的IPリンク**送信）
- ⏱️ iPhone ショートカット連携で 2 時間の自動監視をトリガー可能

## アーキテクチャ

```
iPhone ─── POST /api/monitor ──→ Mac（FastAPI サーバー）
                                    │
                                    ├─ Apple Podcasts DB を監視（5分ごと）
                                    ├─ 新エピソード検出 → 音声取得（ローカルキャッシュ優先）
                                    ├─ mlx-whisper で文字起こし
                                    ├─ Gemini で要約生成（箇条書き中心のHTML/SVGデータ）
                                    └─ Discord にリンク通知 ＋ PWA/Safariで表示
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd backend
pip3 install -r requirements.txt
```

### 2. plist ファイルの準備

```bash
# テンプレートをコピー
cp com.podcast-summary.plist.example com.podcast-summary.plist
```

`com.podcast-summary.plist` を開き、以下を自分の値に書き換え：

| キー | 内容 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で取得した API キー |
| `DISCORD_WEBHOOK_URL` | Discord チャンネルの Webhook URL（任意） |

### 3. Mac 起動時に自動スタート（launchd）

```bash
# ホームディレクトリのプロジェクトフォルダからサービス登録
launchctl load ~/Projects/podcast\ 自動解説/com.podcast-summary.plist

# 停止する場合
launchctl unload ~/Projects/podcast\ 自動解説/com.podcast-summary.plist

# 再起動（設定変更後は必ず実行）
launchctl unload ~/Projects/podcast\ 自動解説/com.podcast-summary.plist
launchctl load  ~/Projects/podcast\ 自動解説/com.podcast-summary.plist
```

### 4. iPhone から閲覧

Mac と iPhone を同じ Wi-Fi に接続し、Safari で：

```
http://<MacのIPアドレス>:8000
```

IP アドレスは以下で確認：
```bash
ipconfig getifaddr en0
```

「ホーム画面に追加」すれば PWA として動作します。

### 5. iPhone ショートカット連携（自動監視トリガー）

iPhone の「ショートカット」アプリで以下を設定すると、Podcasts アプリを開いたときに自動で 2 時間の監視が始まります：

1. ショートカットアプリ → 「オートメーション」→「新規オートメーション」
2. 「App」→「Podcasts」→「開かれたとき」
3. アクションに「URL の内容を取得」を追加
   - URL: `http://<MacのIP>:8000/api/monitor`
   - 方法: `POST`

## ログの確認

```bash
# 通常ログ
tail -f data/server.log

# エラーログ（トラブル時）
tail -f data/server_error.log
```

## 主要 API エンドポイント

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/api/monitor` | POST | 2時間の自動監視を開始（iPhone ショートカットから呼ぶ） |
| `/api/status` | GET | サーバー状態・処理中かどうかを確認 |
| `/api/episodes` | GET | エピソード一覧を取得 |
| `/api/scan` | POST | 今すぐ Apple Podcasts を手動スキャン |
| `/api/process` | POST | 未処理エピソードを今すぐ処理 |

## 技術スタック

| 項目 | 技術 |
|---|---|
| 文字起こし | mlx-whisper medium（Apple Silicon GPU対応）|
| 要約 | Google Gemini Flash (`gemini-3-flash-preview`) |
| バックエンド | Python 3.11 / FastAPI / Uvicorn |
| フロントエンド | PWA（Vanilla HTML/CSS/JS） |
| データベース | SQLite |
| 通知 | Discord Webhook |
| 起動管理 | macOS launchd |

## 注意事項

- `com.podcast-summary.plist` には API キーが含まれるため `.gitignore` に追加済み。Git にはコミットしないこと。
- launchd の環境変数変更後は必ず `unload` → `load` で再起動すること。
- Apple Podcasts DB (`MTLibrary.sqlite`) はロック回避のため一時フォルダにコピーしてから読み取る実装になっています（直接開くと無限待機します）。
- **IPアドレスの動的取得について:** Discord等で外部からアクセスさせる場合のベースURLは、サービス起動時ではなく**実行時（エンドポイント呼び出し時など）に動的解決**させています。`launchd` でのサービス自動起動直後はMacのネットワークが未接続の可能性があり、IPアドレスを定数で保持すると `127.0.0.1` で固定されてしまうためです。
