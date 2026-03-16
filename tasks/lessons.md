# Podcast自動解説プロジェクトの教訓

## 1. Apple Podcasts DB の参照はコピー経由で行う

### 問題
`MTLibrary.sqlite` を直接 `sqlite3.connect()` や `shutil.copy2()` / `open()` などで開こうとすると、macOS の TCC（プライバシー保護）と Apple Podcasts アプリの排他ロックにより、**無制限にハングアップ**する。

### 解決策
OS 標準の `cp` コマンドを `subprocess.run(["cp", "-p", ...])` で呼び出し、**一時ディレクトリへコピーしてからアクセス**する。  
Python の `shutil` や `open()` は TCC に引っかかるが、サブプロセスの `cp` は通る。

```python
subprocess.run(["cp", "-p", str(APPLE_PODCASTS_DB), str(temp_db)], check=False)
```

→ `watcher.py` の `_copy_db_to_temp()` に実装済み。

---

## 2. launchd の環境変数はファイル変更後に必ず再ロード

### 問題
`com.podcast-summary.plist` の `EnvironmentVariables` を変更しても、`launchctl unload / load` しないと反映されない。  
また `load` しただけでは古いプロセスが残る場合があるため、**必ず unload → load の順で実行**すること。

```bash
launchctl unload ~/Projects/podcast\ 自動解説/com.podcast-summary.plist
launchctl load  ~/Projects/podcast\ 自動解説/com.podcast-summary.plist
```

---

## 3. APIキー等の機密情報は絶対に Git にコミットしない

### 問題
Discord Webhook URL や Gemini API キーをファイルに書き込むとき、そのファイルが既に Git 管理下にあると機密情報が漏洩するリスクがある。

### 解決策
- `com.podcast-summary.plist`（実際のキー入り）は `.gitignore` に追加して Git 管理対象外にする
- `com.podcast-summary.plist.example`（プレースホルダ入り）だけを Git にコミットする
- 新しい環境変数を追加するときは `*.example` ファイルも必ず更新すること

---

## 4. 既存の設定値を誤って上書きしない

### 問題
新機能（Discord 通知）の設定を追加する作業中に、Gemini API キーを別の古い文字列で上書きしてしまい、文字起こし完了後の要約ステップで `API_KEY_INVALID` エラーが発生した。

### 防止策
- plist などの設定ファイルを手動で変更するときは、変更前後の diff を必ず確認する
- 1 回のコミットに複数の意味を持たせず、変更箇所を最小限にする

---

## 5. バックグラウンドスレッドの「死」はログに出ない

### 問題
バックグラウンドスレッドが内部でハングアップしても、`server.log` にも `server_error.log` にも何も出力されずに静かに止まる。  
「稼働中メッセージ（監視開始）は来たけど完了通知が来ない」ときはスレッドのハングを疑う。

### 調査手順
1. `tail -f data/server_error.log` でエラーを確認
2. `curl http://localhost:8000/api/status` でサーバー死活確認
3. 手動で `python3 -c "import main; main.run_pipeline()"` を実行してスタックトレースを確認

---

## 6. launchd は ProgramArguments を絶対パスで指定する

### 問題
`python3` を相対パス（`python3`）で指定すると、launchd が PATH を解決できず `ModuleNotFoundError` が発生する。

### 解決策
```xml
<string>/opt/homebrew/bin/python3.11</string>
```
のように Homebrew Python の絶対パスを指定する。

## 7. Discord 通知の UI/UX 改善 (Webhook)

### 課題
Webhook から `description` (最大4000文字) に全文を入れて通知すると、複数エピソードが蓄積した際に Discord の画面が長文で埋め尽くされ、目当てのエピソードを探しにくくなる。
スレッド機能（`thread_name` パラメータ）で逃がそうとしても、Discord の仕様上、最初の投稿内容が親チャンネル側にも大きくプレビューされてしまうため、省スペース化の根本解決にならなかった。

### 解決策
Discord の通常の Text Channel に向けてWebhookから送る場合、**最もコンパクトな表現は「テキストファイルの添付」** である。
`requests.post` の `files` パラメータを使用し、`multipart/form-data` 形式でテキストデータを `.txt` ファイルとしてその場で生成・添付して送信する。
これにより、Discord 上の見た目は「タイトル ＋ 小さなファイルアイコン1行」となり一覧性が劇的に向上した。

```python
    files = {
        "payload_json": (None, json.dumps(payload), "application/json"),
        "file": (
            "summary.txt",
            summary_text.encode("utf-8"),
            "text/plain"
        )
    }
    requests.post(DISCORD_WEBHOOK_URL, files=files)
```

## 8. Discord Webhookでの「ファイルアップロード」と「リンク方式」の違い

### 課題
Discord Webhookを通してHTMLファイル（`.html`）をアップロード（ファイル添付）した場合、iPhoneのDiscordアプリでそれをタップしてもSafariが直接起動せず、「ファイル」アプリに保存するような動作になってしまい、即座に閲覧できない問題があった。

### 解決策
Discord通知の本文に、**FastAPIサーバー上のエンドポイントURLへのリンク** (`[要約を読む](http://IPアドレス:ポート/api/...)`) を含める方式に変更した。
これにより、iPhoneユーザーがリンクをタップするとOSレベルで関連付けられたブラウザ（Safari等）が即座に起動し、作成した自己完結HTMLコンテンツをモバイル最適化・ダークモードの状態でリッチに表示することが可能になった。

---

## 9. FastAPIサーバーにおけるIPアドレスの動的取得

### 課題
上記「リンク方式」にする場合、DiscordからアクセスできるローカルIPアドレスを設定ファイル（`config.py`）にハードコードすると、DHCP環境下やネットワーク変更時にリンク切れを起こす。

### 解決策
`socket` パッケージを使ってホストのIPアドレスを動的に解決する関数を用意し、**モジュール読み込み時ではなく、通知送信時に毎回その関数を呼び出してベースURLを生成**する。
（起動直後の `launchd` による実行時はまだネットワークインターフェースが起きておらず `127.0.0.1` を取得してしまう可能性があるため、定数としての定義は避けること）

```python
def get_server_base_url() -> str:
    """現在のローカルIPアドレスを使用してベースURLを動的に生成する"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return f"http://{ip}:{SERVER_PORT}"
```

---

## 10. AIへのプロンプト：HTMLコンテンツの生成とMarkdownの完全排除

### 課題
LLM（Gemini）に対してHTML出力を要求しても、特に見出しや強調箇所でMarkdown記法（`###`、`**太字**`）が混在してしまい、ピュアなHTMLとして正しくレンダリングできない。

### 解決策
プロンプト内に「警告事項（⚠️）」として、「絶対にMarkdownを使用せず、`<h1>`や`<strong>`などのHTMLタグで出力すること」と二重・三重に強調して指示する。

さらに、プロンプト内で「出力はどのようなCSSで装飾されるか」の**デザイントークン（インラインCSS）も事前に与える**ことで、LLMはそれを前提とした適切なクラス設計付きのHTML構造・SVGタグを返してくれる。

---

## 11. AIへのプロンプト：要約の「トーン＆マナー」の制御

### 課題
単に「要約して」と指示すると、LLMは冗長な文章（「〜について話していました」「〜が重要だと言っています」）を並べがちになり、Podcastを聞いた後にサッと振り返るための「メモ」としては読みにくかった。
また、「印象的な名言」など、不要なセクションを勝手に作ってしまう問題があった。

### 解決策
- **指示の明確化**: 「文章を極力避ける」「キーワードを太字にし、箇条書きでリズミカルに」という出力スタイルを明確に定義した。
- **NG指示の明文化**: 「印象的なハイライトや名言といった項目は作成しないこと」と明確な「禁止事項」を追加することで、出力セクションを制御した。
- **目標の共有**: 単なるフォーマット指示だけでなく、「読者がPodcastを聴き終わった後に『あー、あれね』と一瞬で思い出せるメモ」という究極のペルソナ/目標を提示することで、出力の質が劇的に向上した。

---

## 12. AIによるUI/UXの構造化出力のテクニック（Option A実装）

### 課題
AIからのテキスト出力をただ表示するだけでは、長い文章を読まされている感覚になりUI/UXが低下する。また、フロントエンドとバックエンドが分離している場合、AIの出力結果を後からフロントエンド側でパースして装飾するのは正規表現の限界があり不安定になる。

### 解決策
AI自身に最初から**特定のHTMLクラス付きの構造（見出し、箇条書き、タグ等）を生成させる**ことで、フロントエンドでのパース処理を完全に不要にする。

- プロンプトに具体的なCSSクラス名を指定する（例：`<h1 class="opt-a-header">`, `<div class="opt-a-tags">` など）。
- CSS（デザイントークン）自体もプロンプトに含めて学習・出力させることで、完全に自己完結した美しいHTMLを生成させることができる。
- これにより、フロントエンド側はただ生成されたHTMLをそのまま表示するだけで、複雑でリッチなUI（インサイトのタグ表示、アイコン付きのリスト、美しいテーブルやフローチャート）を実現できる。

---

## 13. マシン移行時の Python バージョン互換性 (型ヒント)

### 課題
旧マシン (MacBook: Python 3.11) で動いていたコードを、新マシン (Mac mini: システムデフォルトの Python 3.9) に `rsync` で移行し APIサーバー (`main.py`) を起動したところ、以下のエラーでクラッシュした。
```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```
原因は、Python 3.10以降で導入された `X | None` のような新しい型ヒント表記（PEP 604）を、Python 3.9環境が解釈できなかったため。

### 解決策
移行元で用いていたPythonの機能（特に構文や型ヒント）に依存している場合があるため、**移行先でも必ず同じマイナーバージョン以上の Python をインストールして `venv` を構築する**。
今回は Mac mini 上で `brew install python@3.11` を行い、指定バージョンのPython (`/opt/homebrew/bin/python3.11`) で `venv` を作り直すことで解決した。
