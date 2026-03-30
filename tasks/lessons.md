# 📓 Podcast 自動解説 開発・運用ナレッジベース

このドキュメントは、プロジェクトの安定稼働と将来のメンテナンスのために、直面した課題とその解決策を構造的に記録したものです。

---

## 🛠 1. 接続・インフラ関連 (iPhone 連携)

### 1.1 IP アドレス変動への対策
- **問題**: ルーターにより Mac の IP アドレスが変わると、iPhone のショートカットが動かなくなる。
- **解決**: ローカルホスト名 (`ooishiayuminoMac-mini.local`) を使用する。
- **ポイント**: これにより、IP アドレスを意識せずに永続的にアクセス可能。

### 1.2 ホスト名 (.local) での 404 (Not Found)
- **問題**: `.local` アドレスだと FastAPI が応答を返さない（IP 直接だと繋がる）。
- **原因**: iPhone は優先的に IPv6 で接続しようとするが、サーバーが IPv4 (`0.0.0.0`) のみで待機していた。
- **解決**: `config.py` の `SERVER_HOST` を `"::"` に設定し、IPv4/IPv6 両対応にする。

---

## 🚀 2. GitHub Pages 連携 (外部公開)

### 2.1 Git 巨大ファイル問題 (100MB 制限)
- **問題**: `venv` 内の ML ライブラリが巨大すぎて `git push` が拒否される。
- **教訓**: **最初の `git add` の前に `.gitignore` を書くこと。**
- **回復策**: 万が一混入した場合は、`.git` を削除して `rm -rf .git` でやり直すのが最も安全。
- **自動化のコツ**: `git push` をプログラムから呼ぶ際は `env["GIT_TERMINAL_PROMPT"] = "0"` を設定し、認証待ちによるフリーズを防止する。

### 2.2 公開設定のポイント
- **ディレクトリ**: `docs/` フォルダを GitHub Pages のルートとして使用。
- **Jekyll 回避**: `docs/.nojekyll` ファイルを置くことで、GitHub 側の不要なビルドをスキップし、CSS/SVG を即座に反映させる。

---

## 🔧 3. 運用・トラブルシューティング

### 3.1 サーバーが起動しない (Address already in use)
- **原因**: 古いプロセスがポート 8000 を掴んだままになっている。
- **コマンド**: `lsof -ti:8000 | xargs kill -9` で強制終了させてから再起動する。

### 3.2 処理が「transcribing」のまま固まる
- **原因**: 以前の強制終了などでステータス更新が途絶えた。
- **対策**: DB を手動でリセットする。
  `sqlite3 data/app.db "UPDATE episodes SET status = 'pending' WHERE status != 'done';"`

### 3.3 稼働確認コマンド集
```bash
# サービスの状態確認（PID と LastExitStatus を確認）
launchctl list com.podcast-summary

# ログ確認（直近20行）
tail -20 data/server.log
tail -20 data/server_error.log

# プロセスのメモリ確認（Activity Monitor相当）
ps -eo pid,rss,vsz,command | grep main.py | grep -v grep

# DB の処理状況確認
sqlite3 data/app.db "SELECT status, COUNT(*) FROM episodes GROUP BY status"
```

---

## 💾 4. メモリ管理（重要）

### 4.1 mlx-whisper がメモリを占有する問題 (2026-03-31)
- **問題**: `transcriber.py` が `import mlx_whisper` をモジュールトップに持つため、
  サーバー起動時に Whisper medium モデルがメインプロセスのメモリに常駐し、
  **10GBを超えるメモリ使用**につながった。
- **原因の本質**: `main.py` が `import transcriber` するだけでMLXモデルが展開される。
  処理が終わってもプロセス内のメモリは解放されない。
- **解決策**: `transcriber.py` の文字起こし処理を **`multiprocessing.Process`（サブプロセス）** で実行。
  - サブプロセス内でのみ `mlx_whisper` をインポート・モデルをロード
  - 文字起こし完了後、サブプロセス終了でOSがMLXモデルのメモリを完全回収
  - メインサーバープロセスは常時 **数十MB以下** を維持
- **効果**: 10.84 GB → 46 MB（約99.6%削減）

### 4.2 VSZ（仮想メモリ）と RSS（実メモリ）の違い
- `ps` コマンドの RSS は Apple Unified Memory の実態を正確に反映しない。
- **正確な把握には Activity Monitor を使う**こと（または `ps -eo pid,rss,vsz,command` でおおよそ確認）。
- mac mini の統合メモリは llm/ml 系ライブラリで一気に到達するので注意。

---

## 🗂 5. データ管理

### 5.1 データの蓄積ルール
| データ | 保存先 | 蓄積方針 |
|--------|--------|----------|
| 音声ファイル | `data/audio/` | 処理完了後に自動削除（`audio_path.unlink()`） |
| 文字起こし | `data/app.db` (transcript カラム) | **30日後に自動削除** |
| 要約HTML | `data/app.db` (summary カラム) + `docs/summaries/` | **30日後に自動削除** |
| エピソードメタ | `data/app.db` (title, podcast等) | 永久保持（軽量なので問題なし） |

### 5.2 自動クリーンアップの仕組み
- `database.cleanup_old_episode_data(days=30)` を実装済み。
- **サーバー起動時（`lifespan` 関数内）に毎回自動実行**される。
- launchd の `KeepAlive=true` によりサーバーが再起動されるたびにチェックが走る。
- 対象: `status = 'done'` かつ `created_at` が30日以前のエピソード
- 処理: `transcript`, `summary` を NULL に更新 + `docs/summaries/{id}.html` を削除
- エピソードのタイトル・再生日時等のメタデータは保持されるため、UI一覧から消えない。

---

## 📖 6. 今後の拡張アイデア
- **自動復旧**: 処理が 1 時間以上「処理中」のままなら自動で `pending` に戻す監視機能。
- **IP 変更検知**: Mac の IP が変わった際に Discord に通知する機能（現在はホスト名解決により優先度低）。
- **エラーエピソードの自動リトライ**: `status = 'error'` のものを翌日再試行する。
- **複数エピソードの並列処理**: サブプロセス化済みなので、`ThreadPoolExecutor` で並列実行しやすい状態になっている。

---
このドキュメントは、同じ苦労を繰り返さないための「資産」である。
最終更新: 2026-03-31
