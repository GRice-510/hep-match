# HEP Match

hep-th の新着論文を、スマホでもPCでも一件ずつ確認する個人用リーダーです。右スワイプで保存、左スワイプで見送り。無料のローカル翻訳を標準にし、DeepLの契約を必須にしません。

## 公開する

1. リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にします。
2. **Actions → Update papers and deploy → Run workflow** を実行します。初回は翻訳モデルの取得も行います。
3. 成功後、`https://grice-510.github.io/hep-match/` を開きます。iPhoneではSafariの共有メニューからホーム画面に追加できます。

公開前は `python -m http.server 8000 --directory site` で画面を確認できます。論文データはActionsで取得するか、後述のローカル実行で生成してください。デモ論文を新着として混ぜることはありません。

## 使い方

- **右スワイプ／保存**：あとで読むリストに追加します。
- **左スワイプ／見送り**：既読にします。元に戻すこともできます。
- **保存一覧**：検索、PDFリンク、Markdown・BibTeX・JSONバックアップの書き出しに対応します。
- **表示設定**：カテゴリ、キーワード、既読を含めるか、原文／日本語訳を選べます。
- 数式はMathJaxで表示します。翻訳に渡す前にTeXの数式を保護します。翻訳は参考訳であり、論文の主張や数値は原文で確認してください。

保存・既読はこのブラウザ内だけに記録されます。端末間の自動同期はありません。ブラウザのデータ削除やホーム画面アイコンの作り直しに備えて、JSONバックアップを保存してください。読み込みは追加マージです。

## 翻訳と費用

### 標準：Argos Translate

GitHub ActionsのCPU上で英語→日本語モデルを動かし、タイトルを優先して、残りの時間でアブストラクトも訳します。APIキー、DeepL契約、Cloudflareは不要です。生成した訳を静的ファイルに含めるため、スマホ側にモデルのインストールは必要ありません。

実行時間に上限を設けています。初回や新着が多い日はすべての訳が揃わないことがあります。未翻訳の論文は原文で利用でき、次回の更新で続きを処理します。翻訳モデルの取得や翻訳が失敗しても、取得済みの新着は原文で配信します。訳の品質はDeepLと同等とは限りません。

公開リポジトリで標準のGitHub-hosted runner（この設定では `ubuntu-latest`）を使う実行時間は無料です。非公開化、有料runnerへの変更、ストレージ上限の引き上げは別の条件になるため、変更前に料金を確認してください。キャッシュと公開用artifactは小さく保ち、artifactの保存期間は1日にしています。

### 対応PC：ブラウザ内翻訳

Chrome等で `Translator` API が利用できる場合は、カードの「この端末で翻訳」から端末内で訳せます。初回は言語モデルをダウンロードすることがあります。APIキーは不要です。対応していないブラウザにはこのボタンを表示しません。iPhone/SafariでもActionsが生成済みの訳は読めます。

### 任意：DeepL

**2026年10月21日に確認した公式案内**では、新規の **DeepL API Developer は累計100万文字まで無料で、枠はリセットされません**。旧 **API Free（月50万文字）** は新規受付終了と案内されています。既存のFree契約と新規Developer契約を混同しないでください。実際の契約・利用可能枠はアカウント画面で確認してください。

DeepLを使う場合だけ、`config.json` の `translation.engine` を `deepl` にし、**Settings → Secrets and variables → Actions** に `DEEPL_API_KEY` を登録します。キーをコードやブラウザに書かないでください。既定では無料用エンドポイントだけを許可し、有料用エンドポイントを使う場合は別途明示的な設定が必要です。アカウントの料金上限も必ず設定してください。無料枠が尽きても有料プランへ自動切替するコードはありません。

DeepLは毎日の事前翻訳に使います。ブラウザからDeepLを直接呼ぶ機能や、公開翻訳proxyは設けていません。

## 設定

`config.json` の `categories` は初期値が `["hep-th"]` です。`hep-ph`、`gr-qc`、`astro-ph.CO` も追加できます。複数カテゴリに載る論文はarXiv IDで一件にまとめます。取得上限に達した場合は画面に警告します。

`translation.engine` は `argos` / `none` / `deepl`。`none` では事前翻訳をせず原文を配信します。`seconds` は翻訳処理の目安となる上限、`max_characters` は一回の翻訳量の上限です。キャッシュには翻訳エンジンと原文のハッシュを含め、改訂で変わった原文の訳を使い回さないようにしています。

新着取得は毎日 **10:17 JST** に予定しています。GitHub Actionsの混雑やarXiv側の事情で遅れる場合があります。公開リポジトリのスケジュールは長期間活動がないと停止する場合があります。画面に表示する最終更新日時とActionsの実行結果を確認してください。

## ローカルで実行する

```bash
python -m pip install -r requirements.txt
python scripts/fetch_papers.py
# 原文だけなら、ここまでで利用可能です。
python -m pip install -r requirements-translation.txt
python scripts/translate_papers.py
python -m http.server 8000 --directory site
```

テスト：

```bash
python -m unittest discover -s tests -v
node --test tests/core.test.mjs
```

## データ取得の範囲と注意点

arXiv APIの投稿日時を基準に直近7日分を取得します。最近になって追加された古い論文のクロスリストは取りこぼすことがあります。改訂のたびに既読を解除する動作にはしていません。arXiv APIには連続アクセスの間隔を設け、取得失敗時は前回のデータを保持します。

外部の無料翻訳サイトを非公式APIで呼び出したり、他人の翻訳proxyを流用したりしません。論文全文PDFを再配布せず、arXivへのリンクを表示します。アクセス解析は入れていません。MathJaxは固定バージョンのCDNから読み込みます。

## 参考・公式資料

- 操作の着想：[ga-swipe](https://github.com/KNakashima37/ga-swipe)。このリポジトリのコード・画像は独自に作成しています。
- [DeepL APIのプラン](https://support.deepl.com/hc/ja/articles/360021200939)
- [DeepL API documentation](https://developers.deepl.com/docs)
- [Argos Translate](https://www.argosopentech.com/)
- [Chrome Translator API](https://developer.chrome.com/docs/ai/translator-api)
- [GitHub Actionsの料金](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [arXiv API利用条件](https://info.arxiv.org/help/api/tou.html)
