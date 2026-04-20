# 株式分析AI Codex handoff: HTML再生成・publish orchestration 実装指示書

- 文書名: 株式分析AI Codex handoff: HTML再生成・publish orchestration 実装指示書
- 作成日: 2026-04-21
- 対象 phase: implementation
- 対象論点: night_update_formalization_and_publish_orchestration_connection
- 位置づけ: `stock_analysis_ai_project_purpose_and_operation_spec_v0_23.md` および 2026-04-20 時点の decision memo 群で固定済みの HTML再生成・publish orchestration 契約を、Codex 実装へ渡すための最新版 handoff
- 旧版扱い: `stock_analysis_ai_codex_handoff_html_render_phase1.md` は本書で置換する。旧版は監査用参考には使えても、実装指示の正本としては使わない

あなたは 株式分析AIプロジェクトの HTML再生成・publish orchestration 実装担当である。
推測で仕様補完しない。未確定事項は残課題へ戻す。既存責務境界を壊さない。

【Codex実行設定】
reasoning_effort: high
reasoning_effort_reason: 現行 spec と decision memo で固定済みの HTML再生成契約、night update formalization、change set 接続、generation staging、latest merged publish、archive monthly、failure handling、URL責務分離、状態語彙分離、stable key deep link、screen root 単位 publish、render / orchestration / storage の責務分離を同時に満たす必要があるため。局所的な renderer 実装では足りず、公開物と正本の境界、受入条件、テスト観点を一貫して満たす抽象設計が必要。

【今回の目的】
現行 spec v0.23 と以下の decision memo 群で固定済みの境界に従い、株式分析AIプロジェクトの静的 HTML再生成基盤および publish orchestration の最小実装を行う。

今回の対象は、正本データ作成そのものではない。既存または今後供給される表示用データと、storage / state 更新後処理から受け取る final record-unit change set を用いて、以下を成立させること。

- 1標準画面 = 1公開HTMLファイルを原則とする画面出力単位
- `generated_html/latest` に last successful publish のみを保持する制御
- `generated_html/generations` に generation 単位 staging / publish 履歴を保持する制御
- `archive/monthly` を successful generation 由来の月次凍結として扱う制御
- path / query / hash の責務分離
- stable key 起点の deep link と画面内アンカー
- `empty` / `none` / `not_applicable` / 未記録 / 評価対象外 / 参照不能 / 再生成失敗 / エラー状態の分離表示
- affected screen 群単位 publish と latest merged publish 契約
- render failure / latest publish failure / archive failure の分離記録
- generation status と運用ログの役割分離
- PC前提の読み取り導線を壊さない最低限のレイアウト契約

【前提として accept-close 済みの事項】
- master_storage completed DDL / migration は accept 済み、close 済み
- 正本は構造化データであり、HTML は再生成表示物である
- 正本更新と HTML 再生成は責務分離する
- `generated_html/latest` は last successful publish のみを保持する
- `generated_html/generations` は generation 単位 staging / publish 履歴を保持する
- `archive/monthly` は successful generation 由来の月次凍結参照である
- change set 単位 publish では、affected screen 群のみを staged generation から差し替え、unrelated screen 群は直前 latest から維持する
- latest 切替失敗時は、直前 latest の保持または復元を優先する
- archive 複製失敗時は、latest を巻き戻さず、publish 成否と archive 成否を分離記録する
- current open issue はなし

【今回の作業範囲】
1. HTML再生成基盤と publish orchestration のコード実装
- screen registry
- screen output contract
- render input contract
- URL state helper
- state label / state mapping
- stable key anchor helper
- payload builder または同等の render input 組立
- publish orchestration
- generation staging 制御
- latest merged publish 制御
- monthly archive export 制御
- generation status 記録と運用ログ記録の最小実装

2. 最低限の画面テンプレート / renderer 実装
- top
- market_overview
- proposal_list
- proposal_detail
- orders
- holdings
- performance
- monthly_review
- reviews
- us_watch
- us_virtual_performance
- us_pilot_performance
- excluded_trades

3. 受入条件を固定する unit test 実装
- latest は successful generation のみ publish される
- failed generation は generations に残っても latest を汚さない
- publish 単位は affected screen 群で扱い、一部成功だけで latest を更新しない
- latest merged publish は unrelated screen を維持する
- affected root 配下 stale file のみ除去される
- archive monthly は latest publish 成功後にのみ実行される
- archive failure で latest が巻き戻らない
- path / query / hash の責務が混線しない
- query に保持すべき共有状態と画面内一時状態が分離される
- 状態語彙が同一表示へ潰れない
- 画面出力単位が契約どおりである
- proposal_detail と monthly_review の自然キー単位出力が成立する
- stable key anchor が proposal / order / position_cycle / review / snapshot / us_virtual / us_pilot を識別できる
- record-unit change set から affected screen 群への接続が decision memo どおりである
- generation status と運用ログが generic failure 1 本へ潰れない

4. 実行入口の最小実装
- 明示的に `final record-unit change set` / `generation_id` / `既定表示条件または対象評価系列` / `publish mode` を受け取る CLI または同等の entry point
- 必要時の `archive 対象期間指定` を受け取れること
- 既定の出力先を repo 相対で扱える構成

【今回の作業範囲外】
- HTML / CSS / JavaScript の見た目最適化
- 色コード、CSS class、icon library の最終固定
- 使用フレームワークの最終選定
- SQLite schema、CREATE TABLE、index、trigger、migration 実装
- market data / broker data / evidence data の取得実装
- 正本データ作成ロジック
- API 実装、SQL 実装、cache 実装
- breakpoint 実数値の最終指定
- SPA 化や client-side state 最適化
- 月次レビュー本文や提案本文の自動生成
- 新しい独立正本、集計専用正本、トップ画面専用正本、月次専用正本の追加
- completed DDL / migration 論点の再検討
- R29 close 済み HTML 表示論点の再オープン
- 自動夜更新ジョブの scheduler 詳細
- URL 最終文法
- `source_index_master.md` 前提の導入

【変更対象ファイル】
以下を編集対象とする。既存ファイルがある場合は更新、ない場合は同責務で新規作成してよい。repo 構成上パス調整が必要な場合は、責務対応表を明示したうえで既存構成へ寄せてよい。

- `src/stock_analysis_ai/html_generation/__init__.py`
- `src/stock_analysis_ai/html_generation/contracts.py`
- `src/stock_analysis_ai/html_generation/screen_registry.py`
- `src/stock_analysis_ai/html_generation/url_state.py`
- `src/stock_analysis_ai/html_generation/state_labels.py`
- `src/stock_analysis_ai/html_generation/payload_builder.py`
- `src/stock_analysis_ai/html_generation/publish_pipeline.py`
- `src/stock_analysis_ai/html_generation/anchor_helper.py`
- `src/stock_analysis_ai/html_generation/renderers/common.py`
- `src/stock_analysis_ai/html_generation/renderers/screens.py`
- `src/stock_analysis_ai/html_generation/cli.py`
- `tests/unit/html_generation/test_contracts.py`
- `tests/unit/html_generation/test_screen_registry.py`
- `tests/unit/html_generation/test_url_state.py`
- `tests/unit/html_generation/test_state_labels.py`
- `tests/unit/html_generation/test_publish_pipeline.py`
- `tests/unit/html_generation/test_renderers.py`
- `tests/unit/html_generation/test_cli.py`

【参照必須ファイル】
- `stock_analysis_ai_project_purpose_and_operation_spec_v0_23.md`
- `stock_analysis_ai_open_issues_management_table.md`
- `stock_analysis_ai_authoring_and_implementation_guide.md`
- `next_phase_selection_after_master_storage_completed_ddl_migration_accept_close_decision_memo.md`
- `master_storage_completed_ddl_and_migration_acceptance_decision_memo.md`
- `night_update_formalization_and_publish_orchestration_connection_decision_memo.md`
- 本 handoff

【実行系へ実際に添付するファイル】
- `stock_analysis_ai_project_purpose_and_operation_spec_v0_23.md`
- `stock_analysis_ai_open_issues_management_table.md`
- `stock_analysis_ai_authoring_and_implementation_guide.md`
- `next_phase_selection_after_master_storage_completed_ddl_migration_accept_close_decision_memo.md`
- `master_storage_completed_ddl_and_migration_acceptance_decision_memo.md`
- `night_update_formalization_and_publish_orchestration_connection_decision_memo.md`
- `stock_analysis_ai_codex_handoff_html_generation_and_publish_orchestration_latest.md`

【実装禁止事項】
- 仕様未記載事項の独自補完
- 未確定事項の本文固定
- `source_index_master.md` 前提の導入
- 新しい独立正本、集計専用正本、トップ画面専用正本、月次専用正本の追加
- HTMLテンプレートを物理 table や SQLite 列へ直結すること
- render 層へ正本更新責務、再生成対象判定責務、publish 可否判定責務、change set 解決責務を持たせること
- generation 失敗時に `generated_html/latest` を更新すること
- generation 失敗時に正本更新を巻き戻すこと
- affected screen 群の一部成功だけで latest を中途半端に更新すること
- latest publish を latest 全体の強制再構築または partial tree 全置換として扱うこと
- stale file 除去を unrelated subtree に広げること
- archive failure を理由に latest を巻き戻すこと
- `empty`、`none`、`not_applicable`、未記録、評価対象外、参照不能、再生成失敗、エラー状態を同一表示へ潰すこと
- path / query / hash の責務を混線させること
- 画面内一時状態を URL の正式契約へ逆流させること
- stable key を無視した deep link 実装
- child 明細用の新しい stable key を仕様補完で追加すること
- 非アクティブ提案、見送り提案、新規建てゼロ提案、候補外、無効化対象を画面都合で黙って除去すること
- change set を screen 差分入力として受けること
- change set を独立工程として切り出し直すこと
- DB trigger に change set 解決、generation 発番、latest publish、archive 複製、render 呼出を持たせること
- silent overwrite
- 例外握りつぶし
- 受入条件未達のまま完了扱い
- 変更対象外ファイルへ不要変更を波及させること

【固定事項】
- 正式閲覧形式は HTML
- 正本は構造化データであり、HTML は再生成表示物
- 正本更新と HTML 再生成は責務分離する
- 正本更新が確定した後に HTML 再生成が失敗しても、正本更新までは巻き戻さない
- 独立正本を追加してはならない
- 一覧画面は索引表示、詳細画面は参照表示、集計画面は派生表示
- `generated_html/latest` は最後に受入条件を満たした successful generation のみを保持する
- `generated_html/generations` は generation 単位 staging / publish 履歴を保持する
- `archive/monthly` は successful generation 由来の月次凍結参照である
- HTML出力単位は原則として標準画面単位とする
- `proposal_detail` は `proposal_id` 単位の個別出力を許容する
- `monthly_review` は月次キー単位の個別出力を許容する
- path = 画面責務または自然な個別参照単位
- query = 評価系列切替、絞込、並び替え、対象期間、表示スコープ等の共有状態
- hash = 同一ページ内 stable key 起点ジャンプ
- query に保持する共有状態と、アコーディオン開閉、列幅、一時ハイライト、スクロール位置等の画面内一時状態は分離する
- query 欠落時は各画面の既定表示条件へ戻してよい
- 未知 query は無視してよいが、既知 query の意味を画面ごとに変えてはならない
- 画面は PC 前提とし、主縦スクロールは 1 本を原則とする
- 上部共通ヘッダおよび一覧画面の絞込・並び替え帯は sticky としてよい
- stable key anchor の標準接頭辞は少なくとも以下を識別できること
  - `proposal-` + `proposal_id`
  - `order-` + `order_id`
  - `position-cycle-` + `position_cycle_id`
  - `review-` + `review_id`
  - `snapshot-` + `snapshot_id`
  - `us-virtual-` + `us_virtual_watch_id`
  - `us-pilot-` + `us_pilot_id`
- 米国株画面では、必要な箇所で現地市場日と日本時間日時を併記できること

【implementation に渡す最小入力契約】
実行入口が受け取る最小入力は、少なくとも以下とする。

- `final record-unit change set`
- `generation_id`
- `default_display_context` または `evaluation_series`
- `publish_mode`
- 必要時の `archive_target_period`

補足:
- `change set` は raw event 差分ではなく、storage / state 更新後処理完了後の最終 record-unit change set とする
- `archive_target_period` は publish mode の詳細化として扱ってよく、system date だけから暗黙推測してはならない
- payload の最終物理フォーマット、CLI 引数の最終文法、API 形式は今回固定しない

【record-unit change set から affected screen 群への接続契約】
少なくとも以下を実装上の固定契約として扱うこと。

A. proposal 記録変化
- 必須再生成対象
  - `top`
  - `proposal_list`
  - `proposal_detail`
- 条件付き再生成対象
  - `market_overview`（proposal 変化に市況メモや市場要点 source の変化が含まれる場合）

B. order / fill / order 系状態変化
- 必須再生成対象
  - `top`
  - `orders`
- 条件付き再生成対象
  - `excluded_trades`（評価対象外区分、算入可否、差分理由の表示に影響する場合）
- 補足
  - order 変化が結果的に holding snapshot や review 更新を生んだ場合、それらは別 record-unit 変化として change set に含める
  - order 変化だけを見て `holdings` や `monthly_review` を暗黙推測で追加してはならない

C. holding snapshot 記録変化
- 必須再生成対象
  - `top`
  - `holdings`
  - `performance`
- 条件付き再生成対象
  - `monthly_review`（月次数値部に影響する場合）

D. review 記録変化
- 必須再生成対象
  - `reviews`
- 条件付き再生成対象
  - `monthly_review`（月次定性部または期間振り返り表示に影響する場合）
  - `market_overview`（市場サマリー source を review 側が保持する場合）
  - `top`（本日要確認事項、重点監視事項、インシデント要約等の表示に影響する場合）

E. us_virtual_watch 記録変化
- 必須再生成対象
  - `us_watch`
  - `us_virtual_performance`

F. us_pilot 記録変化
- 必須再生成対象
  - `us_pilot_performance`
- 条件付き再生成対象
  - `top`（重大インシデント、継続可否、停止理由が top 側集約表示へ出る場合）

G. unrelated screen 群
- affected screen 群に含まれない screen root 群は、直前 latest をそのまま維持する
- unrelated screen を最新化対象へ自動拡張してはならない

【画面責務と最低表示契約】
- `top`: 短時間確認用の集約画面。少なくとも、最新の地合い区分、本日要確認事項、アクティブ提案一覧、未完了注文一覧、未照合件数、保有警戒事項、重大インシデント有無、最新ニュース要約、最新市況メモ、評価系列切替、直近の見送り提案 / 新規建てゼロ提案を扱えること
- `market_overview`: 表示専用の市場概況画面または市場概況詳細画面。独立正本を持たず、日本市場パネルと米国市場パネルを分離して表示できること
- `proposal_list`: 提案記録の索引表示
- `proposal_detail`: 単一 `proposal_id` の正規読取画面
- `orders`: 注文・約定記録の時系列表示
- `holdings`: 最新の保有スナップショット主表示
- `performance`: 既存正本からの派生集計表示
- `monthly_review`: 数値部は既存正本から派生、定性部は review や補助メモ起点の表示
- `reviews`: review 記録の索引表示
- `us_watch`: 米国株ウォッチリスト・仮想売買記録の一覧表示
- `us_virtual_performance`: 米国株ウォッチリスト・仮想売買記録からの派生集計表示
- `us_pilot_performance`: 米国株実売買パイロット記録と関連 order 記録の表示
- `excluded_trades`: 注文・約定記録のうち評価対象外区分の表示

【generation staging 完了条件】
以下をすべて満たした場合のみ staging 完了として扱うこと。

1. `generation_id` が確定している
2. final change set から affected screen root 群が確定している
3. 各対象 root に対する render input が確定している
4. 各対象 root の render が成功している
5. generation status に staging 結果を記録済みである
6. 運用ログに staging 実行結果を記録済みである
7. `generated_html/latest` はまだ未更新である

staging 完了は publish 成功を意味しない。staging と publish は別段階である。

【latest publish 可否判定の最小契約】
latest publish 可と判定してよいのは、少なくとも以下を満たす場合のみ。

- affected screen root 群の staging 完了
- affected screen root 群に render failure が存在しない
- 直前 latest を基底にした merged publish 差替計画が確定している
- affected root 配下で stale file と判定される対象が確定している
- generation status と運用ログに publish 前提条件が記録済みである

上記を満たさない場合、generation 側へ failure を残してよいが、`generated_html/latest` を更新してはならない。

【latest merged publish 契約】
- latest publish は merged publish を原則とする
- 差替単位は file 単位ではなく screen root 単位とする
- affected screen root 配下の旧 subtree は staged generation 側の新 subtree と置換する
- stale file 除去は affected root 配下に限定する
- unrelated root は保持し、削除対象に含めない
- latest 切替失敗時は直前 latest の保持または復元を優先する
- broken latest を標準公開状態として残してはならない

【archive monthly 契約】
- archive monthly は latest publish 成功後の後段責務とする
- staging 完了だけで archive を開始してはならない
- archive monthly を行えるのは successful generation のみ
- archive 要否は `publish_mode` または同等の orchestration 入力で明示する
- 対象期間は orchestration 側で明示される前提とし、system date だけから暗黙推測してはならない
- archive は latest publish と別成否で記録する
- archive failure 時に latest を巻き戻してはならない

【failure handling 契約】
少なくとも以下を分離して扱うこと。

- render failure
- latest publish failure
- archive failure

さらに、記録を以下の 2 層に分離すること。

A. generation status
- generation 単位の構造化状態記録とし、少なくとも以下を区別できること
  - staging result
  - publish result
  - archive result
  - latest 保持または復元有無
- status 名や列名の最終固定は実装へ委譲してよいが、意味差は潰してはならない

B. 運用ログ
- 少なくとも以下を残せること
  - failure 種別
  - 失敗した screen root または処理段階
  - latest への影響有無
  - 保持または復元を行ったか
  - archive のみ失敗したか
  - 再試行または再確認が必要か

generic failure 1 本化は不採用とする。

【render / orchestration / storage の責務分離】
A. storage / state 更新後処理に残す責務
- 正本更新
- 注文照合と reconciliation 更新
- 関連状態更新
- 必要時の holding snapshot 更新
- 必要時の review 更新
- 上記完了後の final record-unit change set 生成

B. orchestration 層に持たせる責務
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

C. render 層に持たせてはならない責務
- 正本更新
- 再生成対象判定
- publish 可否判定
- latest 切替判定
- archive 実行判定
- change set 解決

render 層は、受け取った表示用データを HTML へ変換する表示責務のみに限定すること。

【状態語彙の分離表示契約】
以下は別々に表示分岐できること。単一表示へ潰してはならない。

- `empty`: 当該条件で抽出した結果が 0 件
- `none`: 現在その対象自体が存在しない
- `not_applicable`: 当該系列、列、画面には適用対象外
- 未記録: 本来記録対象となり得るが、まだ正式記録が存在しない
- 評価対象外: 記録済みだが評価系列集計へ算入しない
- 参照不能: 関連リンクまたは証跡参照が現在辿れない
- 再生成失敗: 正本更新後の最新反映が未完了であり、successful generation への publish ができていない
- エラー状態: 入力契約不整合等により、画面自体の生成要件を満たしていない

【受入条件】
1. `generated_html/latest` は、受入条件を満たした successful generation のみを保持すること。
2. generation 失敗時は `generated_html/generations/<generation_id>` 側へ失敗結果または失敗記録を残してよいが、`generated_html/latest` は変更されないこと。
3. 月次確定対象の generation のみ `archive/monthly/<yyyy-mm>` 相当へ凍結複製できること。
4. publish 単位は affected screen 群で扱い、一部だけ成功した中途半端な latest 公開状態を標準としないこと。
5. latest publish は merged publish として扱い、unrelated screen 群を失わないこと。
6. stale file 除去は affected root 配下に限定されること。
7. latest 切替失敗時は、直前 latest の保持または復元を優先し、broken latest を標準状態として残さないこと。
8. archive failure が起きても latest は巻き戻らないこと。
9. screen registry は少なくとも以下の screen を扱えること。
   - `top`
   - `market_overview`
   - `proposal_list`
   - `proposal_detail`
   - `orders`
   - `holdings`
   - `performance`
   - `monthly_review`
   - `reviews`
   - `us_watch`
   - `us_virtual_performance`
   - `us_pilot_performance`
   - `excluded_trades`
10. `proposal_detail` と `monthly_review` は自然キー単位の個別 HTML 出力を行えること。
11. published page には少なくとも `generation_id` と `generated_at` を表示または埋込できること。
12. URL helper は path / query / hash の責務を混線させず、query 欠落時の既定表示と未知 query の無視を実装すること。
13. stable key anchor は少なくとも proposal / order / position_cycle / review / snapshot / us_virtual / us_pilot を識別できること。
14. 画面テンプレート / renderer は表示用 payload を受け取り、物理 table や SQLite 列へ直接依存しないこと。
15. 非アクティブ提案、見送り提案、新規建てゼロ提案、候補外、無効化対象を除外せず識別表示できること。
16. 状態語彙 `empty` / `none` / `not_applicable` / 未記録 / 評価対象外 / 参照不能 / 再生成失敗 / エラー状態 を別々に表示分岐できること。
17. `market_overview` を独立 trigger source として扱わないこと。
18. order 変化が snapshot や review へ波及した場合、screen 側の暗黙推測ではなく post-update change set 側の別 record-unit 変化で扱うこと。
19. generation status と運用ログが別物として残ること。
20. `.venv\Scripts\python.exe -m pytest tests/unit/html_generation -q` または同等コマンドで追加テストを通せること。
21. 変更対象外ファイルへ不要変更を波及させないこと。

【実装上の補足指示】
- 着手前に参照必須ファイルを読み、現行 spec v0.23 と 2026-04-20 decision memo 群に矛盾しない責務分割を確定してから実装すること
- 既存 repo 構成により `src/stock_analysis_ai/html_generation/` 配下が不自然な場合は、同じ責務分割を維持したまま既存構成へ寄せてよい。ただし、変更対象一覧と実変更パスの対応関係を必ず示すこと
- 画面本文の内容生成は最小ダミーでよいが、publish contract、URL contract、state contract、screen registry、generation status / 運用ログ分離、テストは省略しないこと
- renderer 実装では見た目より責務境界、公開契約、失敗時挙動、再現性を優先すること
- `proposal_detail` と `monthly_review` の個別出力で使う自然キーの path 最終文法は実装側で仮定してよいが、仮定内容と影響範囲を明示すること
- status 名、manifest 形式、CLI 引数名、staging から latest への具体的切替アルゴリズムは本文固定外である。実装で具体化してよいが、本 handoff と decision memo の責務境界へ反してはならない

【未確定事項の扱い】
- 未確定事項は残課題として返すこと
- 判断不能箇所は「仮定」と明記すること
- 仮定で進めた場合は影響範囲を列挙すること
- `source_index_master.md` 前提、追加正本、DB直結テンプレート、SPA前提など、現仕様と衝突する仮定は置かないこと
- implementation 中に本文固定外の blocking ambiguity が新たに発生した場合のみ、残課題管理表へ最小単位で戻すこと

【出力形式】
1. 変更要約
2. 変更ファイル一覧
3. 実装内容
4. テスト結果
5. 仮定
6. 残課題
