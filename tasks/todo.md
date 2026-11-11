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

### フェーズ6: 要約のUX/プロンプト改善
- [x] 要約出力をMarkdownから自己完結HTML（SVG図解・テーブル付き）に変更
- [x] UI/UXをダークモード＆モバイル最適化デザインに強化
- [x] Discord通知をファイル添付方式から、HTML要約ページへの直リンク方式に変更
- [x] 長い文章を排除し、サッと振り返れる箇条書き・キーワード中心の洗練されたプロンプトに改善
- [x] 不要な項目（名言・ハイライト）の生成をGeminiに明示的に禁止
- [x] **Option A (構造化サマリーUI)** の実装：タグやアイコン付きリストを利用した流し読みしやすいデザインの適用

### フェーズ7: Mac miniへの環境移行
- [x] プロジェクト移行プランの策定
- [x] 旧マシン(MacBook)における移行準備
- [x] 新マシン(Mac mini)の接続情報（IP、ユーザー名）の確認とSSH鍵登録
- [x] `rsync` を用いたプロジェクト全体の丸ごと転送（.env, app.db, audio等含む）
- [x] 新マシンでの仮想環境(venv)の再構築
- [x] `com.podcast-summary.plist` のユーザー名置換とlaunchctlへの再登録
- [x] 新マシンでの動作確認（APIサーバー起動、フロントエンド表示、ログ確認）

### フェーズ8: メモリ最適化・データライフサイクル管理 (2026-03-31)
- [x] **メモリ問題の特定**: Activity Monitor で `main.py` が 10.84GB を消費していることを発見
- [x] **原因分析**: `import mlx_whisper` がモジュールトップにあることでMLXモデルが常駐
- [x] **`transcriber.py` 修正**: 文字起こし処理を `multiprocessing.Process` で隔離
  - サブプロセス内でのみ `mlx_whisper` をインポート・モデルロード
  - 処理完了後にサブプロセスが終了し、OSがメモリを完全回収
  - 効果: **10.84 GB → 46 MB（99.6%削減）**
- [x] **`database.py` 修正**: `cleanup_old_episode_data(days=30)` を追加
  - 30日以上前のエピソードの `transcript` / `summary` を NULL でクリア
  - 対応する `docs/summaries/{id}.html` ファイルも削除
  - エピソードのメタデータ（タイトル等）は保持
- [x] **`main.py` 修正**: サーバー起動時（`lifespan`）に自動クリーンアップを実行
- [x] `tasks/lessons.md` 更新（メモリ管理・データ管理セクション追加）

---

## 📋 今後の課題（Backlog）

- [ ] エラーエピソードの自動リトライ機能（`status='error'` を翌日 `pending` に戻す）
- [ ] フロントエンドのエラーハンドリング強化
- [ ] 複数エピソードの並列処理（`transcriber.py` がサブプロセス化済みなので実装しやすい）

---

## 📋 現在進行中のタスク

### フェーズ10: オンデマンドキャプチャ方式への転換 (2026-07-09)

「再生した回を全部自動処理」から「聴いている最中にスマホで指定した回だけ処理」へ変更。

- [x] `watcher.py` — 自動一括登録（`check_and_register_new_episodes`）を廃止し、
  `get_recent_episodes_with_status()`（一覧取得のみ・登録なし）と
  `capture_episode(apple_episode_id)`（1件だけ登録、None なら直近再生中の回）に置き換え
- [x] `database.py` — `get_episode_by_apple_id()` を追加
- [x] `pipeline.py` — 2時間監視ループ（`_monitor_loop` / `start_monitor`）を削除。
  `run_pipeline` はスキャンせず pending のみ処理。`capture_and_process()` を追加。
  エラー状態の回を再キャプチャすると pending に戻してリトライ
- [x] `main.py` — `GET /api/recent`（最近再生した回の一覧）と `POST /api/capture`
  （body なし＝今聴いている回、`{"apple_episode_id": N}`＝指定回）を追加。
  `/api/scan` と `/api/monitor` は削除
- [x] `config.py` — `WATCH_INTERVAL_SECONDS` / `MONITOR_DURATION_SECONDS` /
  `WATCH_SINCE_HOURS` を削除し `RECENT_HOURS = 24` に統合
- [x] フロントエンド — 監視ボタンを「回を選んで要約」ピッカーに置き換え。
  「▶ 今聴いている回を要約する」ボタン＋最近再生した回のリスト（タップでキャプチャ）
- [x] launchd サービスの再起動による新コード反映と動作確認
  （`/api/recent` 0.2秒で3件返却、`/api/capture` で「今聴いている回」を正しく特定、
  要約済みの回は再処理せず「要約済みです」を返すことを実機確認）
- [x] `/api/recent` `/api/capture` を sync ハンドラに変更（Apple Podcasts DB の
  コピーがブロックしてもイベントループ全体が固まらないように）
- [ ] **iPhone ショートカットの更新（ユーザー作業）**: 呼び先を
  `POST /api/monitor` → `POST /api/capture`（body なし）に変更する。
  タップすると「今聴いている回」だけが処理される

### フェーズ9: launchd 設定の修正と自動実行の復旧 (2026-05-20)
- [x] `backend/config.py` — `WATCH_SINCE_HOURS = 24` の設定追加
- [x] `backend/watcher.py` — 監視対象期間に `WATCH_SINCE_HOURS` を適用
- [x] launchd ジョブのアンロード (`launchctl unload`)
- [x] 正しい plist ファイルのコピー (`com.podcast-summary.plist` -> `~/Library/LaunchAgents/`)
- [x] launchd ジョブの再ロード (`launchctl load`)
- [x] 稼働状況・プロセスの動作確認 (ログ確認、ポート8000のリスン確認)


