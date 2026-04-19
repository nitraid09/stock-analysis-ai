あなたは 株式分析AIプロジェクトの HTML再生成・出力接続 実装担当である。
推測で仕様補完しない。未確定事項は残課題へ戻す。既存責務境界を壊さない。

【Codex実行設定】
reasoning_effort: high
reasoning_effort_reason: 複数仕様書横断で、HTML出力単位、latest / generations / archive、render / orchestration / storage の責務境界、URL状態、空状態・失敗状態、受入条件を同時に満たす必要があるため。単純な局所実装ではなく、公開物と正本の境界を守る抽象設計とテスト設計が必要。

【目的】
R29までで確定した HTML実装方式・再生成パイプライン・出力接続契約に従い、株式分析AIプロジェクトの静的HTML再生成基盤の最小実装を行う。

対象は、正本データそのものの作成ではなく、既存または今後供給される表示用データを受けて、以下を成立させること。
- 1標準画面 = 1公開HTMLファイルを原則とする画面出力単位
- `generated_html/latest` を last successful publish のみ保持する publish 制御
- `generated_html/generations` を generation単位 staging / publish履歴として保持する制御
- `archive/monthly` を successful generation 由来の月次凍結として扱う制御
- path / query / hash の責務分離
- stable key 起点の deep link と画面内アンカー
- `empty` / `none` / `not_applicable` / 未記録 / 評価対象外 / 参照不能 / 再生成失敗 / エラー状態の分離表示
- PC前提の読み取り導線を壊さない最低限のレイアウト契約
- 受入条件を満たした generation のみを latest へ publish する挙動

【今回の作業範囲】
1. HTML再生成基盤のコード実装
- screen registry
- screen output contract
- URL state helper
- state label / state mapping
- publish orchestration
- generation staging と latest publish 制御
- monthly archive export 制御
- stable key anchor helper
- render input contract

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
- path / query / hash の責務が混線しない
- query に保持すべき共有状態と画面内一時状態が分離される
- 状態語彙が同一表示へ潰れない
- 画面出力単位が契約どおりである
- proposal_detail と monthly_review の自然キー単位出力が成立する
- 影響画面群の publish 単位がまとめて扱われる

4. 実行入口の最小実装
- 明示的に payload / generation_id / publish mode を受け取る CLI または同等の entry point
- 既定の出力先を repo 相対で扱える構成

【今回の作業範囲外】
- HTML / CSS / JavaScript の見た目最適化
- 色コード、CSS class、icon library の最終固定
- 使用フレームワークの最終選定
- SQLite schema、CREATE TABLE、index、trigger
- market data / broker data / evidence data の取得実装
- 正本データ作成ロジック
- API 実装、SQL 実装、cache 実装
- breakpoint 実数値の最終指定
- SPA 化や client-side state 最適化
- 月次レビュー本文や提案本文の自動生成
- 新しい独立正本の追加
- source_index_master.md 前提の導入

【変更対象ファイル】
以下のファイルを編集対象とする。既存ファイルがある場合は更新、ない場合は同パスで新規作成してよい。

- src/stock_analysis_ai/html_generation/__init__.py
- src/stock_analysis_ai/html_generation/contracts.py
- src/stock_analysis_ai/html_generation/screen_registry.py
- src/stock_analysis_ai/html_generation/url_state.py
- src/stock_analysis_ai/html_generation/state_labels.py
- src/stock_analysis_ai/html_generation/payload_builder.py
- src/stock_analysis_ai/html_generation/publish_pipeline.py
- src/stock_analysis_ai/html_generation/anchor_helper.py
- src/stock_analysis_ai/html_generation/renderers/common.py
- src/stock_analysis_ai/html_generation/renderers/screens.py
- src/stock_analysis_ai/html_generation/cli.py
- tests/unit/html_generation/test_contracts.py
- tests/unit/html_generation/test_screen_registry.py
- tests/unit/html_generation/test_url_state.py
- tests/unit/html_generation/test_state_labels.py
- tests/unit/html_generation/test_publish_pipeline.py
- tests/unit/html_generation/test_renderers.py
- tests/unit/html_generation/test_cli.py

【参照必須ファイル】
- stock_analysis_ai_project_purpose_and_operation_spec_v0_21.md
- stock_analysis_ai_open_issues_management_table_r29_update_draft.md
- canslim_authoring_and_implementation_guide.md

【現チャットで再添付不要な常設ファイル】
- なし
- 本案件では `source_index_master.md` を前提にしない。Codex は、実際に添付された仕様書と本プロンプトのみを根拠に判断すること。

【次チャット / 実行系へ実際に添付するファイル】
- stock_analysis_ai_project_purpose_and_operation_spec_v0_21.md
- stock_analysis_ai_open_issues_management_table_r29_update_draft.md
- canslim_authoring_and_implementation_guide.md
- stock_analysis_ai_codex_handoff_html_render_phase1.md

【実装禁止事項】
- 仕様未記載事項の独自補完
- 新しい独立正本、集計専用正本、トップ画面専用正本、月次専用正本の追加
- HTMLテンプレートを物理 table 直結前提で実装すること
- render 層へ正本更新責務、再生成対象判定責務、publish 可否判定責務を持たせること
- generation 失敗時に `generated_html/latest` を更新すること
- generation 失敗時に正本更新を巻き戻すこと
- `empty`、`none`、`not_applicable`、未記録、評価対象外、参照不能、再生成失敗、エラー状態を同一表示へ潰すこと
- path / query / hash の責務を混線させること
- 画面内一時状態を URL の正式契約へ逆流させること
- stable key を無視した deep link 実装
- 非アクティブ提案、見送り提案、新規建てゼロ提案、候補外、無効化対象を画面都合で黙って除去すること
- silent overwrite
- 例外握りつぶし
- 受入条件未達のまま完了扱い
- 未確定事項の本文固定

【固定事項】
- 正式閲覧形式は HTML
- 正本は構造化データであり、HTML は再生成表示物
- 独立正本を追加してはならない
- 一覧画面は索引表示、詳細画面は参照表示、集計画面は派生表示
- `generated_html/latest` は最後に受入条件を満たした successful generation のみを保持する
- `generated_html/generations` は generation単位 staging / publish履歴を保持する
- `archive/monthly` は successful generation 由来の月次凍結参照
- path = 画面責務または自然な個別参照単位
- query = 評価系列切替、絞込、並び替え、対象期間、表示スコープ等の共有状態
- hash = 同一ページ内の stable key 起点ジャンプ
- query に保持する共有状態と、アコーディオン開閉、列幅、一時ハイライト、スクロール位置等の画面内一時状態は分離する
- 画面は PC 前提とし、主縦スクロールは1本を原則とする
- 上部共通ヘッダおよび一覧画面の絞込・並び替え帯は sticky としてよい
- 1標準画面 = 1公開HTMLファイルを原則とし、proposal_detail と monthly_review は自然キー単位の個別ファイル出力を許容する

【受入条件】
1. `generated_html/latest` は、受入条件を満たした successful generation のみを保持すること。
2. generation 失敗時は `generated_html/generations/<generation_id>` 側へ失敗結果または失敗記録を残してよいが、`generated_html/latest` は変更されないこと。
3. 月次確定対象の generation のみ `archive/monthly/<yyyy-mm>` へ凍結複製できること。
4. publish 単位は affected screen 群で扱い、一部だけ成功した中途半端な latest 公開状態を標準としないこと。
5. 画面テンプレート / renderer は表示用 payload を受け取り、物理 table や SQLite 列へ直接依存しないこと。
6. screen registry は少なくとも以下の画面を扱えること。
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
7. URL helper は path / query / hash の責務を混線させず、query 欠落時の既定表示と未知 query の無視を実装すること。
8. stable key anchor は少なくとも proposal / order / position_cycle / review / snapshot / us_virtual / us_pilot を識別できること。
9. proposal_detail と monthly_review は自然キー単位の個別HTML出力を行えること。
10. 一覧系・集計系画面は query と hash を用いて表示状態と画面内ジャンプを扱えること。
11. 状態語彙 `empty` / `none` / `not_applicable` / 未記録 / 評価対象外 / 参照不能 / 再生成失敗 / エラー状態 を別々に表示分岐できること。
12. published page には少なくとも generation_id と generated_at を表示または埋込できること。
13. 非アクティブ提案、見送り提案、新規建てゼロ提案、候補外、無効化対象を除外せず識別表示できること。
14. 共有表示部品は表示責務のみに限定し、正本更新や publish 判定を持たないこと。
15. `.venv\Scripts\python.exe -m pytest tests/unit/html_generation -q` または同等コマンドで追加テストを通せること。
16. 変更対象外ファイルへ不要変更を波及させないこと。

【実装上の補足指示】
- まず、参照必須ファイルを読み、R29 反映済み仕様に対して矛盾しない責務分割を確定してから実装すること。
- 既存 repo 構成により `src/stock_analysis_ai/html_generation/` 配下が不自然な場合は、同じ責務分割を維持したまま既存構成へ寄せてよい。ただし、その場合でも変更対象一覧と実変更パスの対応関係を明示すること。
- 画面本文の内容生成は最小ダミーでよいが、publish contract、URL contract、state contract、screen registry、テストは省略しないこと。
- レンダリング結果の見た目よりも、責務境界、公開契約、失敗時挙動、再現性を優先すること。

【未確定事項の扱い】
- 未確定事項は残課題として返す
- 判断不能箇所は「仮定」と明記する
- 仮定で進めた場合は影響範囲を列挙する
- `source_index_master.md` 前提、追加正本、DB直結テンプレート、SPA前提など、現仕様と衝突する仮定は置かない

【出力形式】
1. 変更要約
2. 変更ファイル一覧
3. 実装内容
4. テスト結果
5. 仮定
6. 残課題
