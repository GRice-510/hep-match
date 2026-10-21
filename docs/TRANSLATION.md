# 翻訳方式と無料利用の条件

確認日：2026年10月21日。料金・提供条件は変更されるため、登録時は各サービスの公式ページとアカウント画面で確認してください。

## 今回の実装で使えるもの

| 方法 | APIキー | 実装・検証状況 |
|---|---|---|
| 原文の閲覧とスワイプ | 不要 | 実装済み。最初は原文を表示します。 |
| Argos Translateの事前翻訳 | 不要 | GitHub Actionsで実行済み。ただし物理用語の誤訳が目立ち、試験的な参考訳として扱います。 |
| Chromeの端末内Translator API | 不要 | 対応ブラウザにだけボタンを表示。言語モデルが使える実端末での翻訳品質は未検証です。 |
| DeepL API | 必要 | 接続コード・利用上限確認・エラー時の処理を実装済み。実際のアカウントとの疎通は未検証です。 |

### 無料訳についての実測上の注意

初回のarXiv取得は171件でした。Argosでタイトル171件、アブストラクト107件を翻訳し、一回の文字数上限で停止しました。未翻訳分は次回以降に処理し、同じ原文はキャッシュから再利用します。件数は初回実行時点の値で、現在の値はアプリ画面と `site/data/latest.json` を確認してください。

実際の訳には、物理で使う `order` を「注文」とする例や、`conformal field theories` の訳が崩れる例がありました。**ArgosをDeepLと同等の研究用翻訳としては勧めません。** 初期表示を原文にし、「日本語の参考訳を表示」を押した場合だけ訳を表示するようにしています。数式を翻訳から外して文字列を保持する処理はありますが、これだけで文章の意味の正しさを保証するものではありません。

追加登録をせずに使う場合は、原文で仕分けし、対応PCでは「この端末で翻訳」を補助に使う運用が出発点です。ChromeのTranslator APIは公式案内上デスクトップ向けで、モバイルでは動作しません。スマホでも、Actionsで事前生成した訳は表示できます。

## DeepLは無料で使えるか

現在の公式案内では、新規向け **DeepL API Developer** は **累計100万文字**までです。この枠は毎月リセットされません。旧 **API Free（月50万文字）** は新規受付が終了しています。既存のFree契約がある場合と、新規でDeveloper契約を作る場合では条件が異なります。

Web版やデスクトップ版のDeepL契約と、API契約は区別してください。今回、利用者のDeepLアカウント情報やAPIキーは取得していません。

使用する場合は `config.json` の `translation.engine` を `deepl` にし、GitHubの **Settings → Secrets and variables → Actions** に `DEEPL_API_KEY` を登録します。キーをチャットに貼ったり、公開ファイルへ書き込んだりする必要はありません。

接続先は既定で `https://api-free.deepl.com` です。契約で指定された接続先・利用枠をDeepLの管理画面と公式API資料で確認してください。`https://api.deepl.com` を使うには `DEEPL_API_BASE` と `ALLOW_PAID_DEEPL=true` を明示的に設定する必要があります。このフラグは有料利用が可能な接続先への誤送信を防ぐためのもので、個々のキーが無料プランか有料プランかを判定する機能ではありません。アカウント側の上限設定も必要です。

今回のコードに、有料プランへ自動的にアップグレードする処理はありません。翻訳できなくても原文の閲覧は続けられます。

## 継続的な無料枠を持つ別サービス

以下は公式条件を調べた候補です。**今回のコードにはまだ接続しておらず、実アカウントでの疎通・翻訳品質も未検証です。**

### Azure Translator F0

公式料金表では **月200万文字まで無料**です。Azureアカウントを作り、翻訳リソースの価格レベルとして **F0** を選ぶ必要があります。S1などの従量課金プランと混同しないでください。長期の自動翻訳を考える場合、毎月更新される無料枠の候補になります。物理論文の訳の品質は、導入前に実際のタイトル・アブストラクトで比較する必要があります。

### Gemini API無料枠

一部モデルには無料枠がありますが、利用可能モデルとリクエスト上限はアカウント・提供時点で異なります。Google AI Studioで確認が必要です。無料枠の入力・出力は製品改善に使われる条件があるため、未公開原稿や個人情報を送る用途とは分けて検討してください。今回のアプリが扱う公開arXivメタデータを翻訳する候補にはなりますが、有料プロジェクトのキーを使えば無料とは限りません。

## 公式資料

- [DeepL APIのプラン](https://support.deepl.com/hc/ja/articles/360021200939)
- [DeepL APIの認証](https://developers.deepl.com/docs/getting-started/auth)
- [Argos Translate](https://www.argosopentech.com/)
- [Chrome Translator API](https://developer.chrome.com/docs/ai/translator-api)
- [Azure Translatorの料金](https://azure.microsoft.com/en-us/pricing/details/translator/)
- [Gemini APIの料金](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini APIの課金と無料枠](https://ai.google.dev/gemini-api/docs/billing/)
- [GitHub Actionsの料金](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

公開リポジトリの標準GitHub-hosted runnerは実行時間が無料です。今回の設定はその範囲を使い、翻訳用GPUや有料クラウドサーバーを作成しません。リポジトリを非公開にしたり、有料runnerに変更したりする際は条件を再確認してください。
