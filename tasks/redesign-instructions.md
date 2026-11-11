# 指示書: Podcast 自動解説 v2 — 「今ゼロから作るなら」再設計プラン

作成日: 2026-07-08
対象: 別セッションの Claude Code（この指示書だけで作業を開始できるように書いてある）
現行コードの場所: `backend/`（FastAPI + パイプライン）、`frontend/`（PWA）、`docs/summaries/`（公開HTML）、`data/app.db`（SQLite）

---

## 0. 前提: 現行システムの理解

動いているもの（**壊さないこと**）:

- Apple Podcasts の再生履歴 DB（`MTLibrary.sqlite`）を `cp` コピー経由で監視 → 再生済みエピソードを検出
- 音声を取得 → mlx-whisper（サブプロセス隔離、メモリ99.6%削減済み）で文字起こし
- Gemini Flash に**自己完結HTML（SVG図解つき）を直接生成させて** `docs/summaries/{id}.html` に保存
- `git push` で GitHub Pages に公開、Discord Webhook でリンク通知
- iPhone ショートカット → `POST /api/monitor` で2時間監視モード起動
- launchd で Mac mini に常駐

運用ノウハウは `tasks/lessons.md` に集約されている。**着手前に必読**（TCC回避、IPv6、git push の GIT_TERMINAL_PROMPT=0 など、再設計でも同じ罠を踏む）。

### 現行の弱点（再設計の動機）

1. **要約が「HTML文字列」としてしか存在しない** — LLMにHTMLを直接吐かせているため、デザイン変更・横断検索・再利用（一覧ページ、ダイジェスト、統計）が一切できない。最大の構造的負債。
2. **flat な script 群** — `backend/*.py` が素の import で結合。パッケージ構造・型付き設定・テストがない。
3. **公開側に「一覧」がない** — `docs/summaries/` に170件以上のHTMLが溜まっているのに、入口となる index も検索もない。Discord のリンクを失うと過去の要約に辿り着けない。
4. **要約コミットが main の履歴を汚す** — 「Add summary: ...」がコード履歴に混ざる。
5. **単発エピソード処理のみ** — 170件分の文字起こし資産があるのに、横断的な価値（検索、関連エピソード、週次ダイジェスト）を何も生んでいない。

---

## 1. 再設計の核となる方針（これだけは守る）

### 方針A: 「LLMはJSONを返す。HTMLはテンプレートが作る」

要約生成を2段に分離する:

```
transcript ──LLM──▶ summary.json（構造化データ）──Jinja2──▶ episode.html
```

- LLM への指示は「このJSONスキーマで要約せよ」（pydantic モデル + Gemini の structured output / response_schema を使用）
- スキーマ案: `title, podcast_name, published_at, duration, one_liner（一言要約）, topics[]（見出し+箇条書き+タイムスタンプ）, keywords[], takeaways[], guest_names[]`
- HTML/SVG のデザインは Jinja2 テンプレート側で管理。**デザイン変更が「テンプレート修正+全件再レンダリング」だけで済む**ようになる
- `summary.json` は DB（またはファイル）に永続化。これが後述のすべての新機能の土台

### 方針B: 正データは SQLite、公開物はビルド成果物

- `data/app.db` に transcript 全文と summary JSON を保存（現状 transcript を保存しているか確認し、なければ追加）
- `docs/` 以下はいつでも全削除→全再生成できる状態にする（静的サイトジェネレータ的発想）

### 方針C: 過剰設計しない

個人用・単一マシン・SQLite・launchd という現構成は正しい。Docker/Celery/Postgres/クラウド化は**やらない**（非ゴール）。

---

## 2. 新しいプロジェクト構成

```
podcast-summary/
├── pyproject.toml          # uv 管理。requirements.txt は廃止
├── .env.example
├── src/podcast_summary/
│   ├── config.py           # pydantic-settings。環境変数+.env で型付き設定
│   ├── models.py           # Episode / Summary の pydantic モデル（JSONスキーマの源泉）
│   ├── db.py               # SQLite アクセス（現 database.py）
│   ├── sources/
│   │   └── apple_podcasts.py   # 現 watcher.py + downloader.py
│   ├── transcribe.py       # 現 transcriber.py（サブプロセス隔離は維持）
│   ├── summarize.py        # Gemini structured output → Summary モデル
│   ├── render.py           # Jinja2: Summary → HTML、index.html、検索データ生成
│   ├── publish.py          # git push（現 pipeline.py の git 部分）
│   ├── notify.py           # Discord
│   ├── pipeline.py         # 状態機械: pending→transcribing→summarizing→rendered→published
│   ├── server.py           # FastAPI（現 main.py）
│   └── templates/          # episode.html.j2 / index.html.j2 / digest.html.j2
├── frontend/               # 管理用PWA（ほぼ現状維持）
├── docs/                   # GitHub Pages（全再生成可能なビルド成果物）
├── data/                   # app.db, audio/, logs（gitignore）
├── tests/                  # pytest（最低限: models, render, watcher のタイムスタンプ変換）
└── tasks/
```

CLI エントリポイント（デバッグ・再処理を楽にする）:

```
uv run podcast-summary serve            # サーバー起動
uv run podcast-summary process <id>     # 1件を手動処理
uv run podcast-summary rerender --all   # テンプレ変更後に全HTML再生成
uv run podcast-summary rebuild-index    # index/検索データ再生成
```

---

## 3. 「魅力を上げる」機能ロードマップ（優先順）

### ⭐ P1: エピソード一覧 + 検索ページ（最重要・体験が一変する）

- `docs/index.html`: 全エピソードをカード表示（番組名でグルーピング、日付順、one_liner とキーワードタグを表示）
- `docs/search-index.json`: 全件の `{id, title, podcast, keywords, one_liner, takeaways}` を書き出し、クライアントJSで即時全文フィルタ（170件程度なら外部ライブラリ不要。件数が増えたら FlexSearch 等を検討）
- スマホファースト。既存要約のダークモード調のトーンを踏襲
- **これで「Discordリンクを踏む」以外の入口が初めてできる**

### ⭐ P2: 過去170件のバックフィル

- 既存の `docs/summaries/*.html` は正データがない（HTMLしかない）ため、DB に transcript が残っている件は summary.json を再生成、残っていない件は既存HTMLからタイトル・キーワードを抽出して search-index に最低限載せる
- 既存URL `summaries/{id}.html` は**維持**（Discord に貼られた過去リンクを殺さない）

### P3: 週次ダイジェスト

- launchd（または既存サーバーの定期処理）で毎週日曜、その週の summary.json 群を LLM に渡して「今週聴いた番組の横断まとめ」を生成 → `docs/digests/2026-W28.html` + Discord 通知
- 「複数番組を聴く人」にとって唯一無二の価値になる。ここが最大の差別化ポイント

### P4: タイムスタンプ・ディープリンク

- Whisper のセグメントタイムスタンプを summary.json の各 topic に紐付け
- 要約ページの各トピックに `▶ 12:34` を表示 → Apple Podcasts の URL スキームか、`<audio>` タグ + ローカル音声で該当位置から再生
- 「要約を読んで気になった所だけ聴き直す」動線が完成する

### P5: 関連エピソード / 「聴いた記憶に聞く」

- summary.json の埋め込みベクトル（Gemini embedding API）を SQLite に保存
- 各要約ページ下部に「関連エピソード」3件を表示
- 発展: `POST /api/ask` で「◯◯について話してた回どれ？」に答えるエンドポイント（PWA から利用）

### P6: 運用の磨き込み

- `GET /api/health`（最終処理時刻・pending件数・ディスク残量）を Discord に日次レポート
- 要約コミットを `gh-pages` 相当の別ブランチ or 別リポジトリに分離し、main をコード専用に戻す
- ログローテーション、`app.db` の日次バックアップ（`sqlite3 .backup`）

---

## 4. 実装フェーズ（別セッションでの進め方）

各フェーズ完了ごとにコミット。**フェーズ2完了までは現行システムを止めない**（新旧並走）。

| フェーズ | 内容 | 完了条件 |
|---|---|---|
| 1 | `pyproject.toml` + `src/` レイアウトへ移行、pydantic-settings 化、既存ロジックをそのまま移植 | 現行と同じ動作で `uv run podcast-summary serve` が起動し、新規1エピソードが従来どおり処理される |
| 2 | 方針A実装: models.py + structured output + Jinja2 テンプレート | 新規エピソードが summary.json 経由で生成され、見た目が現行同等以上 |
| 3 | P1 一覧+検索、P2 バックフィル | index.html から全過去回に到達・検索できる。既存URLが生きている |
| 4 | P3 週次ダイジェスト | 手動トリガーで1本生成→Discord通知が動く。その後スケジュール化 |
| 5 | P4〜P6 | 各機能ごとに個別判断（着手前にユーザーに優先度を確認してよい） |

### 移行時の注意（lessons.md より再掲 + 追加）

- `.gitignore` を最初に書く（venv/モデルファイルの混入は致命傷）
- Apple Podcasts DB は必ず `cp -p`（WAL/SHM 込み）でコピーしてから読む
- サーバーは `::`（IPv4/IPv6両対応）で bind
- git 自動 push は `GIT_TERMINAL_PROMPT=0`
- transcriber のサブプロセス隔離と「`get()` を `join()` より先に呼ぶ」修正（2026-07 の未コミット diff）は必ず引き継ぐ
- launchd plist はユーザー名ハードコードに注意（`.example` 方式を維持）

## 5. 非ゴール

- Docker / クラウドデプロイ / Postgres / ジョブキュー基盤（Celery等）
- 多ユーザー対応・認証
- リアルタイム文字起こし
- Apple Podcasts 以外のソース対応（設計上 `sources/` で拡張可能にはしておくが、実装しない）
