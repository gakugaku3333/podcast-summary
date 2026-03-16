# 🎧 Podcast 自動解説 (GitHub Pages 連携版)

Apple Podcasts で再生したエピソードを**自動で文字起こし・要約**し、GitHub Pages 経由でどこからでも閲覧可能にするアプリ。

## 🌟 新機能: GitHub Pages 連携
要約された HTML が自動的に GitHub の `docs/summaries/` フォルダへプッシュされます。
これにより、**外出先（別の Wi-Fi や 4G/5G）**からでも Discord のリンクをクリックするだけで要約が読めるようになりました！

- **公開URL**: `https://gakugaku3333.github.io/podcast-summary/summaries/[エピソードID].html`

## 🚀 使い方

### 1. iPhone からのトリガー
- iPhone のショートカットで以下の URL を `POST` 実行（Podcasts アプリを開いたときなど）。
- **推奨 URL**: `http://ooishiayuminoMac-mini.local:8000/api/monitor`
- これにより 2時間の自動監視が始まり、再生されたエピソードを順次処理します。

### 2. 手動操作 (Web UI)
- Safari 等で `http://ooishiayuminoMac-mini.local:8000` にアクセス。
- **「更新」ボタン**: Apple Podcasts DB を再スキャン。
- **「2時間監視」ボタン**: 監視モードを強制起動。

## ⚙️ セットアップ & 運用

### 重要: GitHub Pages の設定 (初回のみ)
1. GitHub で `podcast-summary` という Public リポジトリを作成。
2. **Settings > Pages** で以下を設定：
   - `Build and deployment > Source`: `Deploy from a branch`
   - `Branch`: `main` / `/docs`
   - **Save** を押す。

### トラブルシューティング
#### 1. GitHub へのプッシュが 404 または拒否される
- `backend/venv/` などの巨大なライブラリが Git に入っていないか確認してください。
- `.gitignore` で `backend/venv/` を除外済みです。
- 認証エラーが出る場合は、Mac 側で `git push` が通る状態（SSHキー等）か確認してください。

#### 2. ポート 8000 が既に使用されている (Address already in use)
- 古いプロセスが残っている可能性があります。
- 解決: `lsof -ti:8000 | xargs kill -9` を実行してから再起動。

#### 3. 処理が止まっている
- `launchd` のログを確認: `tail -f data/server_error.log`
- サービス再起動: `launchctl unload ...` -> `launchctl load ...`

## 🛠 技術構成
- **文字起こし**: mlx-whisper (Apple Silicon GPU)
- **要約**: Gemini Flash (HTML/SVG 出力)
- **通知**: Discord Webhook
- **公開**: GitHub Pages (Static HTML)
