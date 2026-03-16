# タスク管理

## ✅ 完了済み

### フェーズ1: コア機能
- [x] `config.py` — 設定管理（API キー、パス、プロンプト等を一元管理）
- [x] `database.py` — SQLite でエピソードの処理状態を管理
- [x] `watcher.py` — Apple Podcasts DB を監視し再生済みエピソードを検出
- [x] `downloader.py` — ローカルキャッシュ優先で音声ファイルを取得
- [x] `transcriber.py` — mlx-whisper（Apple Silicon GPU）で文字起こし
- [x] `summarizer.py` — Gemini API で日本語要約を生成
- [x] `requirements.txt` — Python 依存パッケージ定義

### フェーズ2: API + フロントエンド
- [x] `main.py` — FastAPI サーバー（パイプライン統合 + API + 静的ファイル配信）
- [x] `index.html` / `style.css` / `app.js` — モバイルファースト PWA
- [x] `manifest.json` / `sw.js` — PWA 対応（ホーム画面追加）

### フェーズ3: 通知・自動化
- [x] `notifier.py` — Discord Webhook で要約完了を通知
- [x] `/api/monitor` エンドポイント — iPhone ショートカットから 2 時間監視をトリガー
- [x] `com.podcast-summary.plist` — launchd によるバックグラウンド常駐

### フェーズ4: バグ修正・安定化
- [x] Apple Podcasts DB の TCC ロック問題を `cp` コマンド経由で回避
- [x] launchd 環境での `ffmpeg` PATH 問題を解決
- [x] Gemini API キーの誤上書きを発見・修正
- [x] リファクタリング（import 整理、不要定数削除、CSS 重複排除）
- [x] セキュリティ対応（plist を `.gitignore` に追加、.example テンプレートを作成）

### フェーズ5: ドキュメント・クロージング
- [x] `README.md` — 全機能・セットアップ手順を網羅した最新版に更新
- [x] `tasks/lessons.md` — 今回の教訓を体系的に記録
- [x] Git 初期化と `main` ブランチへのコミット

### フェーズ6: 要約のUX/プロンプト改善（今回実施）
- [x] 要約出力をMarkdownから自己完結HTML（SVG図解・テーブル付き）に変更
- [x] UI/UXをダークモード＆モバイル最適化デザインに強化
- [x] Discord通知をファイル添付方式から、HTML要約ページへの直リンク方式に変更
- [x] 長い文章を排除し、サッと振り返れる箇条書き・キーワード中心の洗練されたプロンプトに改善
- [x] 不要な項目（名言・ハイライト）の生成をGeminiに明示的に禁止
- [x] **Option A (構造化サマリーUI)** の実装：タグやアイコン付きリストを利用した流し読みしやすいデザインの適用

## 📋 今後の課題（Backlog）

- [ ] エラーエピソードの自動リトライ機能
- [ ] 要約・音声ファイルの定期クリーンアップ
- [ ] フロントエンドのエラーハンドリング強化
- [ ] 複数エピソードの並列処理

### フェーズ7: Mac miniへの環境移行 (新規)
- [x] プロジェクト移行プランの策定
- [x] 旧マシン(MacBook)における移行準備
- [x] 新マシン(Mac mini)の接続情報（IP、ユーザー名）の確認とSSH鍵登録
- [x] `rsync` を用いたプロジェクト全体の丸ごと転送（.env, app.db, audio等含む）
- [x] 新マシンでの仮想環境(venv)の再構築
- [x] `com.podcast-summary.plist` のユーザー名置換とlaunchctlへの再登録
- [x] 新マシンでの動作確認（APIサーバー起動、フロントエンド表示、ログ確認）
