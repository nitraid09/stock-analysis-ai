# 株式分析AI 夜更新正式化導線 / publish orchestration 接続 decision memo

- 文書名: 株式分析AI 夜更新正式化導線 / publish orchestration 接続 decision memo
- 対象 issue_id: night_update_formalization_and_publish_orchestration_connection
- 対象 phase: decision
- chat_stage: decision
- 作成日: 2026-04-20
- 位置づけ: master_storage completed DDL / migration accept-close 後に、夜更新正式化導線 / publish orchestration 接続について、現行仕様のままで close できる範囲、implementation へ渡せる責務境界、spec 本文へ戻さず memo 側で保持すべき決定事項を整理するための decision memo

---

## 1. 目的

本 memo は、master_storage completed DDL / migration の accept-close が完了した前提で、夜更新正式化導線 / publish orchestration 接続について、implementation 着手前に必要な decision boundary を一括で固定することを目的とする。

今回は、implementation、Codex handoff 作成、仕様書本文改版、残課題管理表更新には進まない。現行仕様のままで確定できる範囲、未確定として残す範囲、反映先、次段 implementation へ渡せる責務境界を明確化することに限定する。

本 memo は、close 済み事項の再オープンや本文固定外の技術詳細の先取りを目的としない。特に、R29 close 済み HTML 表示論点、master_storage completed DDL / migration の再受入、completed CREATE TABLE / index / trigger / migration 手段の再検討には戻らない。

---

## 2. 参照前提

本 memo は、少なくとも以下を現行根拠として用いる。

1. `stock_analysis_ai_project_purpose_and_operation_spec_v0_23.md`
2. `stock_analysis_ai_authoring_and_implementation_guide.md`
3. `stock_analysis_ai_open_issues_management_table.md`
4. `next_phase_selection_after_master_storage_completed_ddl_migration_accept_close_decision_memo.md`
5. `master_storage_completed_ddl_and_migration_acceptance_decision_memo.md`

加えて、以下を accept-close 済み前提として扱う。

- master_storage completed DDL / migration は accept 済み、close 済み
- 正本は構造化データであり、HTML は再生成表示物である
- 正本更新と HTML 再生成は責務分離する
- `generated_html\latest` は last successful publish のみを保持する
- `generated_html\generations` は generation 単位 staging / publish 履歴を保持する
- `archive\monthly` は successful generation 由来の月次凍結参照である
- change set 単位 publish では、affected screen 群のみを staged generation から差し替え、unrelated screen 群は直前 latest から維持する
- latest 切替失敗時は、直前 latest の保持または復元を優先する
- archive 複製失敗時は、latest を巻き戻さず、publish 成否と archive 成否を分離記録する
- active open issue は current 台帳上なし

本 memo は、上記 close 済み事項を再オープンしない。

---

## 3. 今回の対象と非対象

### 3.1 対象

今回の対象は、以下に限定する。

- 夜更新正式化の開始条件をどこまで decision として固定するか
- change set と affected screen 群解決の接続契約
- 必須再生成対象、条件付き再生成対象、unrelated screen 維持条件の整理
- generation staging 完了条件
- publish 可否判定の最小契約
- latest publish を merged publish として成立させる最小条件
- affected screen 群だけを安全に差し替える契約
- stale file を残さない条件
- archive monthly の切出条件
- publish success と archive success の分離記録
- render failure / latest publish failure / archive failure の分離
- generation status と運用ログの最小記録粒度
- orchestration 層に持たせる責務
- render 層に持たせてはならない責務
- storage / state 更新後処理に残す責務
- implementation に渡せる粒度まで今回 close できる事項と、close できない事項の切り分け
- 残課題管理表更新要否
- 次段 implementation へ進んでよい条件

### 3.2 非対象

今回の非対象は、以下とする。

- R29 close 済み HTML / CSS / JavaScript 見た目論点の再検討
- completed CREATE TABLE 文、index SQL、trigger SQL、migration CLI / tool / transaction の再検討
- master_storage completed DDL / migration の再受入判定
- 実装コード作成
- Codex handoff 作成
- 仕様書本文更新
- 残課題管理表更新
- DB、API、スクレイピング、broker 連携の技術実装詳細
- URL 最終文法
- `source_index_master.md` 前提の導入

---

## 4. 検討結果の第三者点検

本チャットで得た初回結論を第三者目線で点検した結果、方向性自体は妥当であったが、implementation へ渡すには一部論点の詰めが不足していた。以下のとおり整理し直す。

### 4.1 妥当だった点

- 夜更新正式化導線 / publish orchestration 接続を、master_storage close 後の次工程として選んだ順序は妥当である。
- implementation 直行ではなく、先に decision で責務境界を詰めるべきとした判断は妥当である。
- R29 close 済み HTML 表示論点へ戻さない、という除外判断は妥当である。
- 正本更新、change set 解決、generation staging、latest publish、archive monthly、failure handling を一連の orchestration 問題として扱うべき、という方向性は妥当である。

### 4.2 詰め直しが必要だった点

#### A. 夜更新正式化の開始条件がやや粗かった

「夜更新が正式化標準枠である」という事実だけだと、implementation 側が毎営業日強制実行の固定ジョブと誤読する余地がある。spec は、正式判断または状態更新が存在しない日は、夜更新を毎営業日の必須作業として固定しないと明記している。

修正として、開始条件は「storage / state 更新後処理が、当該回の正式判断または状態更新を既存記録単位へ確定し、その結果から change set を生成できること」に限定する。

#### B. change set の受け口を raw 変更差分として扱う余地が残っていた

注文変化や提案変化の raw 入力から直接 affected screen 群へ跳ぶ理解だと、snapshot 更新や review 更新を含む標準正式化順序と噛み合わない。spec は、正本更新と関連状態更新を確定した後に change set を解決する順序を取っている。

修正として、orchestration が受け取る change set は、storage / state 更新後処理が完了した後の**最終 record-unit change set**を前提とする。order 変化が snapshot や review を派生的に生んだ場合、その変化は raw order から暗黙推測させるのではなく、post-update change set に別 record-unit 変化として含める。

#### C. 必須再生成対象、条件付き再生成対象、unrelated 維持条件が一部曖昧だった

一覧と詳細を持つ standard screen 群の多くは spec から直接引けるが、`market_overview`、`monthly_review`、`excluded_trades` は過不足なく扱わないと under-publish と over-publish の双方が起こり得る。

修正として、record-unit 変化ごとに必須再生成対象と条件付き再生成対象を切り分ける。特に `market_overview` は独立 trigger source とせず、top または市場メモ由来表示の source が変化する回に条件付きで含める。`monthly_review` は snapshot 数値部または review 定性部の source が変化した回に含める。`excluded_trades` は order 系変化のうち評価対象外区分の表示に影響する回に含める。

#### D. generation status と運用ログの役割分離が不足していた

failure を 1 本の generic failure として扱うと、successful generation、published latest、archived monthly の成否が潰れる。spec は generation status と運用ログを分離して扱う前提である。

修正として、generation status は generation 単位 lifecycle の構造化記録、運用ログは原因、影響、保持 / 復元有無、再試行要否を残す監査ログに分ける。

#### E. archive monthly の切出条件を calendar 推測へ寄せる余地があった

月次凍結の要否をシステム日付だけで決めると、再実行、再生成、月跨ぎ補正時に再現性が落ちる。

修正として、archive monthly の要否は publish mode または同等の orchestration 入力で明示し、対象期間も orchestration 側で明示される前提にする。実装時に system date だけから暗黙推測してはならない。

#### F. stale file 除去の範囲が明文化不足だった

stale file を消す、だけだと latest 全体の再構築や unrelated subtree 破壊へ誤解が及び得る。

修正として、stale file 除去は **affected screen root 配下に限定**する。unrelated screen 群は直前 latest を保持し、除去対象に含めない。

---

## 5. 根拠整理

### 5.1 spec 上すでに固定済みの事項

現行 spec では、少なくとも以下が固定済みである。

1. 夜更新時の標準的正式化順序は、注文照合、関連状態更新、必要時の snapshot / review 更新、change set 解決、generation 出力、successful generation のみ latest publish、月次対象時のみ archive 複製、失敗時 latest 維持である。
2. 再生成ジョブが受け取る最小入力単位は、少なくとも change set、generation 識別子、既定表示条件または対象評価系列、publish mode である。
3. orchestration 層は、change set 受領、影響画面群解決、generation 発番、staging 出力指示、受入判定、latest publish、archive 複製、運用ログ記録を担う。
4. render 層は、受け取った表示用データを HTML へ変換する表示責務のみに限定し、正本更新、再生成対象判定、publish 判定を持たない。
5. latest publish は partial tree 全置換ではなく、affected screen 群だけを差し替える merged publish を原則とする。
6. latest 切替失敗時は、直前 latest の保持または復元を優先する。
7. archive 複製失敗時は、latest を巻き戻さず、publish 成否と archive 成否を分離記録する。
8. `us_virtual_watch_header` と `us_pilot_header` は completed schema 対象だが、夜更新正式化は変化がある日を原則とし、日本株系と同一頻度の毎営業日必須を要求しない。

今回の decision は、これらを変更するものではなく、implementation に渡せる粒度まで明文化するものである。

### 5.2 guide 上の段階運用

guide では、decision は推奨案提示、問題点・根拠・影響・修正方針の提示、確定事項と未確定事項の分離を行う段階であり、implementation は変更対象、禁止事項、受入条件、未確定事項の扱いまで固定された後に進む段階である。

したがって、orchestration 契約が implementation へ渡せる粒度まで固まっていない状態で implementation へ直行するのは順序誤りである。一方で、今回の decision でその粒度まで閉じられるなら、次段は implementation に進める。

### 5.3 current 台帳の状態

current open issues 台帳では、active open issue はなしである。したがって、今回の整理で新規 open issue を自動的に増やす必要はない。decision 後にも本文固定外の blocking ambiguity が残る場合のみ、必要最小限で起票すれば足りる。

---

## 6. decision boundary の固定

### 6.1 夜更新正式化の起動条件

本論点は **close** とする。

夜更新正式化の開始条件は、「night update 時刻に到達したか」ではなく、「storage / state 更新後処理が、当該回の正式判断または状態更新を既存記録単位へ確定し、その結果から change set を生成できるか」で判定する。

したがって、以下を原則とする。

- 正式判断または状態更新が存在しない回は、orchestration を開始しない
- 日本株系では、夜更新は正式化標準枠だが、毎営業日の必須強制実行とはしない
- 米国株系では、正式判断、条件到達、除外、終了、重大または軽微インシデント、関連注文・約定参照更新等の変化がある日を原則とする
- `market_overview` のような表示専用 screen の都合だけで orchestration を開始してはならない

起動条件を「変化ありの正式記録回」に限定することで、空 generation 発行、無意味な latest 切替、運用ログ汚染を防ぐ。

### 6.2 change set と affected screen 群解決の接続契約

本論点は **close** とする。

orchestration が受け取る change set は、raw イベント差分ではなく、storage / state 更新後処理が完了した後の**最終 record-unit change set**とする。screen 差分を input として受けてはならない。

したがって、以下を原則とする。

- change set は独立した主工程ではなく、夜更新正式化順序の中の 1 段として扱う
- storage / state 更新後処理は、正本更新、照合状態更新、関連状態更新、必要時 snapshot / review 更新までを先に完了させる
- その後、orchestration が final change set を受領し、affected screen 群を解決する
- render 層は、change set 解決責務を持たない
- DB trigger は、change set 解決、generation 発番、latest publish、archive 複製、render 呼出の責務を持たない

この整理により、order 変化が snapshot や review へ波及した場合も、screen 側の独自推測なしに扱える。

### 6.3 必須再生成対象、条件付き再生成対象、unrelated screen 維持条件

本論点は **close** とする。

affected screen 群の標準接続は、少なくとも以下を原則とする。

#### A. proposal 記録変化

必須再生成対象:

- `top`
- `proposal_list`
- `proposal_detail`

条件付き再生成対象:

- `market_overview`（proposal 変化に、市況メモや市場要点 source の変化が含まれる場合）

#### B. order / fill / order 系状態変化

必須再生成対象:

- `top`
- `orders`

条件付き再生成対象:

- `excluded_trades`（評価対象外区分、算入可否、差分理由の表示に影響する場合）

補足として、order 変化が結果的に holding snapshot や review 更新を生んだ場合、それらは別 record-unit 変化として change set に含める。order 変化だけを見て `holdings` や `monthly_review` を暗黙推測で追加してはならない。

#### C. holding snapshot 記録変化

必須再生成対象:

- `top`
- `holdings`
- `performance`

条件付き再生成対象:

- `monthly_review`（月次数値部に影響する場合）

#### D. review 記録変化

必須再生成対象:

- `reviews`

条件付き再生成対象:

- `monthly_review`（月次定性部または期間振り返り表示に影響する場合）
- `market_overview`（市場サマリー source を当該 review 側が保持する場合）
- `top`（本日要確認事項、重点監視事項、インシデント要約等の表示に影響する場合）

#### E. us_virtual_watch 記録変化

必須再生成対象:

- `us_watch`
- `us_virtual_performance`

#### F. us_pilot 記録変化

必須再生成対象:

- `us_pilot_performance`

条件付き再生成対象:

- `top`（重大インシデント、継続可否、停止理由が top 側集約表示へ出る場合）

#### G. unrelated screen 群

affected screen 群に含まれない screen root 群は、直前 latest をそのまま維持する。unrelated screen を最新化対象へ自動拡張してはならない。

### 6.4 generation staging 完了条件

本論点は **close** とする。

generation staging 完了は、単に一部の HTML が出力された状態ではなく、affected screen 群の publish 候補として整った状態を指す。少なくとも以下を満たした場合のみ staging 完了と扱う。

1. generation 識別子が確定している
2. final change set から affected screen root 群が確定している
3. 各対象 root に対する render input が確定している
4. 各対象 root の render が成功している
5. generation status に staging 結果を記録済みである
6. 運用ログに staging 実行結果を記録済みである
7. `generated_html\latest` はまだ未更新である

staging 完了は、latest publish 成功を意味しない。staging と publish は別段階である。

### 6.5 publish 可否判定の最小契約

本論点は **close** とする。

latest publish 可否判定は、affected screen 群全体を単位として行う。一部 root だけ成功した中途半端な latest 状態を標準としない。

publish 可と判定してよい最小条件は、少なくとも以下とする。

- affected screen root 群の staging 完了
- affected screen root 群に render failure が存在しない
- 直前 latest を基底にした merged publish 差替計画が確定している
- affected root 配下で stale file と判定される対象が確定している
- generation status と運用ログに publish 前提条件が記録済みである

上記を満たさない場合、generation 履歴側へ failure を残してよいが、`generated_html\latest` を更新してはならない。

### 6.6 latest publish 契約

本論点は **close** とする。

latest publish は **merged publish** を原則とする。partial tree 全置換でも、最新ディレクトリ全体の作り直しでもない。直前 latest を基底にし、affected screen 群だけを staged generation から差し替え、unrelated screen 群はそのまま維持する。

最小契約は、少なくとも以下とする。

- 差替単位は file 単位ではなく screen root 単位とする
- affected screen root 配下の旧 subtree は、staged generation 側の新 subtree と置換する
- stale file 除去は affected root 配下に限定する
- unrelated root は保持し、削除対象に含めない
- latest 切替失敗時は、直前 latest の保持または復元を優先する
- broken latest を標準公開状態として残してはならない

この契約により、change set 単位 publish と latest の閲覧整合性を両立させる。

### 6.7 archive monthly 契約

本論点は **close** とする。

archive monthly は、latest publish 成功後の後段責務とする。staging 完了だけで archive を開始してはならない。

最小契約は、少なくとも以下とする。

- archive monthly を行えるのは successful generation のみ
- archive 要否は publish mode または同等の orchestration 入力で明示する
- 対象期間は orchestration 側で明示される前提とし、system date だけから暗黙推測してはならない
- archive は latest publish と別成否で記録する
- archive failure 時に latest を巻き戻してはならない

これにより、月次凍結の再実行性と publish の安定性を両立できる。

### 6.8 failure handling 契約

本論点は **close** とする。

failure handling は、少なくとも以下を分離して扱う。

- render failure
- latest publish failure
- archive failure

さらに、記録も以下の 2 層に分離する。

#### A. generation status

generation 単位の構造化状態記録として、少なくとも以下を区別できることを前提とする。

- staging result
- publish result
- archive result
- latest 保持または復元有無

status 名や列名の最終固定は implementation に委ねてよいが、上記の意味差は潰してはならない。

#### B. 運用ログ

運用ログでは、少なくとも以下を残せることを前提とする。

- failure 種別
- 失敗した screen root または処理段階
- latest への影響有無
- 保持または復元を行ったか
- archive のみ失敗したか
- 再試行または再確認が必要か

failure を generic failure へ 1 本化すると、successful generation / published latest / archived monthly の成否が混線するため不採用とする。

### 6.9 orchestration / render / storage の責務分離

本論点は **close** とする。

#### A. storage / state 更新後処理に残す責務

- 正本更新
- 注文照合と reconciliation 更新
- 関連状態更新
- 必要時の holding snapshot 更新
- 必要時の review 更新
- 上記完了後の final record-unit change set 生成

#### B. orchestration 層に持たせる責務

- final change set 受領
- affected screen 群解決
- generation 発番
- staging 出力指示
- generation staging 完了判定
- latest publish 可否判定
- latest merged publish 実行
- archive monthly 実行
- generation status 記録
- 運用ログ記録

#### C. render 層に持たせてはならない責務

- 正本更新
- 再生成対象判定
- publish 可否判定
- latest 切替判定
- archive 実行判定
- change set 解決

render 層は、受け取った表示用データを HTML へ変換する表示責務のみに限定する。

---

## 7. close / keep open / split 判定

### 7.1 今回 close できる事項

以下は、今回 **close** とする。

- 夜更新正式化の起動条件
- change set の受け口を final record-unit change set とすること
- affected screen 群解決の責務を orchestration 層へ固定すること
- 必須再生成対象、条件付き再生成対象、unrelated screen 維持条件の最小契約
- generation staging 完了条件
- latest publish 可否判定の最小契約
- latest merged publish 契約
- affected root 配下 stale file 除去契約
- archive monthly の切出条件と publish 成否との分離
- render failure / latest publish failure / archive failure の分離
- generation status と運用ログの役割分離
- storage / orchestration / render の責務分離
- 残課題管理表更新不要の判定
- 次段を implementation に進めてよいという判定

### 7.2 今回 keep open としない事項

今回対象範囲の中で、decision として keep open に残すべき blocking 論点はない。implementation に必要な責務境界は、現行仕様の範囲内で閉じられる。

### 7.3 今回 split としない事項

change set、latest publish、archive monthly、failure handling を独立工程へ split しない。これらは夜更新正式化導線 / publish orchestration 接続の構成要素として一体で扱う。

---

## 8. residual と最小残件化方針

### 8.1 今回 close できないが issue 化不要の事項

以下は本文固定外または implementation 詳細であり、今回 close / keep open 判定の対象外とする。これらは現時点で open issue 化しない。

- generation status の物理列名、status 文字列、manifest 形式
- staging から latest への具体的ファイル切替アルゴリズム
- archive 複製媒体やコピー手段
- 自動夜更新ジョブの scheduler 詳細
- URL 最終文法
- CLI や API の呼出形式

これらは implementation で具体化してよいが、今回固定した責務境界と矛盾してはならない。

### 8.2 最小残件化案

今回の decision 後に、implementation で本文固定外の blocking ambiguity が新たに発生した場合のみ、残課題管理表へ最小単位で追加する。その場合も、以下を原則とする。

- close 済み事項を再オープンしない
- 物理実装方式の差異だけで issue を増殖させない
- implementation を止める blocking ambiguity に限って起票する
- spec 本文へ戻す必要がない限り、current 台帳の最小追加に留める

---

## 9. 文書反映要否

### 9.1 仕様書本文

**反映不要** とする。

理由は以下のとおりである。

- 今回の結論は project 恒久仕様の追加ではなく、現行 spec で固定済み高位原則を implementation へ渡せる粒度まで decision memo 化したものである
- spec には、夜更新正式化順序、責務分離、latest / generations / archive 契約の高位原則が既に反映済みである
- この段階で spec 本文へ decision 整理を逆流させると、SSOT と作業判断メモの責務が混線する

### 9.2 残課題管理表

**更新不要** とする。

理由は以下のとおりである。

- current 台帳上 active open issue はなし
- 今回は、新規未確定事項の発生ではなく、implementation-ready な責務境界の整理である
- 本文固定外の技術詳細はまだ blocking ambiguity へ至っていない
- この段階で issue を追加すると、close 済み事項や decision 済み事項を不必要に reopen しやすい

### 9.3 本 memo

今回の文書反映先は、本 memo とする。

本 memo は、夜更新正式化導線 / publish orchestration 接続 decision の根拠整理、詰め直し結果、implementation 着手可否の判定を保持する正式な decision memo である。spec 本文や current open issues の代替ではないが、今回の反映先としてはこれが適切である。

---

## 10. implementation 着手可否

### 10.1 判定

次段は **implementation に進んでよい** と判定する。

### 10.2 implementation に渡せる最小入力契約

implementation に渡す最小入力契約は、現行 spec の固定事項を前提に、少なくとも以下とする。

- final record-unit change set
- generation 識別子
- 既定表示条件または対象評価系列
- publish mode
- 必要時の archive 対象期間指定

最後の archive 対象期間指定は、publish mode の詳細化として扱ってよく、system date だけへ依存してはならない。

### 10.3 implementation で守るべき最小責務境界

implementation では、少なくとも以下を破ってはならない。

- render 層へ正本更新責務、再生成対象判定責務、publish 判定責務を持たせない
- failed generation で `generated_html\latest` を更新しない
- affected screen 群の一部成功だけで latest を中途半端に更新しない
- latest publish を latest 全体の強制再構築や partial tree 全置換と誤解しない
- stale file 除去を unrelated subtree に広げない
- archive failure を理由に latest を巻き戻さない
- change set を独立工程として切り出し直さない

---

## 11. 結論

master_storage completed DDL / migration accept-close 後の次工程として行った夜更新正式化導線 / publish orchestration 接続 decision は、今回の整理で implementation へ渡せる粒度まで閉じられたと判断する。

今回 close した中核は、以下である。

1. 起動条件は「変化ありの正式記録回」であること
2. change set は final record-unit change set として受けること
3. affected screen 群解決は orchestration 層の責務であること
4. staging 完了と publish 可否判定を分離すること
5. latest publish は affected root 群単位の merged publish であること
6. archive monthly は latest publish 後の後段責務であり、成否を分離記録すること
7. render / publish / archive failure を潰さず分離すること
8. generation status と運用ログを分離すること
9. storage / orchestration / render の責務境界を再オープンしないこと

したがって、仕様書本文および残課題管理表は更新せず、本 memo を decision の正式反映先とし、次段は implementation に進むのが妥当である。
