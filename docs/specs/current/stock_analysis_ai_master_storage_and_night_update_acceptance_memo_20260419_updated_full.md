# 株式分析AI 受入メモ

## 1. 文書情報
- 文書名: 正本保存基盤・夜更新正式化導線 実装受入メモ
- 対象論点ID:
  - 主対象: `master_storage_completed_schema_and_physical_detail_decision_boundary`
  - 関連受入基盤: `master_storage_and_night_update_formalization_minimum_implementation_boundary`
- 作成日: 2026-04-19
- 判定段階: acceptance memo
- 対象コミット: 未記載（本メモは今回共有された completed schema・physical detail 実装差分を対象とする）
- 判定: **accept（残課題付き）**

## 2. 目的
本メモは、正本保存基盤・夜更新正式化導線について、前段で受け入れた最小実装を前提に、completed schema・physical detail の反映実装が受入可能かを判定し、受入根拠、受け入れていない範囲、残課題、追加の仕様書修正要否を明文化するために作成する。

本メモは、R29 close 済みの HTML 実装論点の受入メモではない。今回の対象は、あくまで `master_storage` を中核とする正本保存基盤の physical scaffold、child / supporting table の更新粒度、`payload_json` の許容境界、`evidence_ref` の親境界、米国株2表の formalization 境界の実装整合である。

## 3. 受入対象
今回の受入対象は、反映済み仕様に基づく completed schema・physical detail の整合実装であり、主対象は以下とする。

- `src/stock_analysis_ai/master_storage/__init__.py`
- `src/stock_analysis_ai/master_storage/contracts.py`
- `src/stock_analysis_ai/master_storage/change_set.py`
- `tests/unit/master_storage/test_contracts.py`
- `tests/unit/night_update/test_orchestrator.py`

今回の受入対象には、以下を含めない。

- `src/stock_analysis_ai/night_update/` の責務再設計
- `src/stock_analysis_ai/html_generation/contracts.py` の再設計
- `src/stock_analysis_ai/html_generation/publish_pipeline.py` の再設計
- R29 close 済みの HTML 画面仕様、URL state、状態語彙、PC 前提レイアウト制約の再検討
- completed CREATE TABLE 文、index、trigger、migration の完成版確定

## 4. 判定結果
判定は **accept（残課題付き）** とする。

理由は以下のとおりである。

1. 既存の SQLite 中核方針と 11 表構成を維持したまま、child / supporting table から `payload_json` を排除し、header 系 table の補助情報用途へ押し戻している。
2. logical row で `payload_json` を露出させない契約と、physical schema で child / supporting table に `payload_json` を残さない契約が、contract と repository の双方で明示されている。
3. child 更新粒度が一律の親キー単位置換ではなく、`proposal_target` immutable、`order_fill` append-only、`holding_snapshot_position` の `snapshot_id` 単位確定集合、`evidence_ref` の append / superseded 相当更新へ table 別に整理されている。
4. `evidence_ref` の親許容が header 系中心へ絞られ、`proposal` / `order` / `holding_snapshot` / `review` / `us_pilot` 以外は reject されるため、初版標準にない child 直付けや `position_cycle` 直付けが逆流していない。
5. `change_set` は `evidence_ref` の record-unit 解決を header 系中心へ揃えており、`position_cycle` / `us_virtual_watch` 直結を前提としない。
6. night update / HTML 側は再設計されておらず、既存の publish semantics、latest keep / restore、archive 分離、R29 close 済み境界を壊していない。
7. テストは `tests/unit/master_storage tests/unit/night_update` で 25 passed、`tests/unit/html_generation` で 23 passed を確認しており、今回の変更が既存 publish semantics を破壊していないことも補助的に確認できている。

## 5. 受入根拠

### 5.1 正本保存基盤の整合
- 正本中核は引き続き `master/storage/master_storage.sqlite3` である。
- 11 表構成は維持されている。
- `proposal_target`、`order_fill`、`holding_snapshot_position`、`position_cycle_registry`、`evidence_ref` は child / supporting table として維持されている。
- child / supporting table の physical 列は最小 typed scaffold に寄せられており、legacy の child / supporting `payload_json` schema を許容しない。
- header 系 table だけが supplemental 用 `payload_json` を保持している。

### 5.2 contract 整合
- `ALL_TABLES` は 11 表を維持している。
- `PARENT_TABLES`、`CHILD_TABLES`、`SUPPORTING_TABLES` の責務分離は維持されている。
- `EVIDENCE_PARENT_TYPES` は `proposal` / `order` / `holding_snapshot` / `review` / `us_pilot` に限定され、header 系中心の親境界へ揃っている。
- logical snapshot 検証では、全 table の logical row に対して `payload_json` の露出を reject している。
- `review_header` は単一 primary subject を要求している。
- `order_status` と `reconciliation_status` は別責務で維持されている。
- `evidence_ref` は 1 行 1 親系統を要求している。

### 5.3 repository / 更新粒度の整合
- `proposal_target` は、同一 `proposal_id` で既存集合との差分更新を reject しており、formalized 後 immutable として扱っている。
- `order_fill` は、同一 `(order_id, fill_id)` に対する内容上書きを reject しており、append-only を維持している。
- `holding_snapshot_position` は、同一 `snapshot_id` の既存集合との差し替えを reject しており、snapshot 単位の確定集合として扱っている。
- `evidence_ref` は sibling 参照を消去せず、同一 `(parent_type, parent_id, reference_path)` 行だけを state 更新できる実装となっている。
- `position_cycle_registry` は supporting table として upsert されるが、`evidence_ref` の標準親対象には入っていない。

### 5.4 change set / night update 導線の整合
- `TABLE_TO_RECORD_UNIT` は従来どおり record-unit 解決を維持している。
- `EVIDENCE_PARENT_UNIT` は `proposal` / `order` / `holding_snapshot` / `review` / `us_pilot` に限定されている。
- `evidence_ref` 由来で `position_cycle` や `us_virtual` を record-unit 解決しないため、初版標準外の親接続が orchestration 側へ逆流していない。
- `tests/unit/night_update/test_orchestrator.py` では、非標準 evidence 親が generation 前に reject されることを確認している。
- `us_pilot` は当該行変更時のみ changed record-unit へ入ることを確認しており、米国株 2 表を日本株系と同じ毎営業日必須 formalization へ戻していない。

### 5.5 既存 HTML 側との境界整合
- 今回の変更ファイルに `src/stock_analysis_ai/html_generation/contracts.py`、`src/stock_analysis_ai/html_generation/publish_pipeline.py` は含まれていない。
- したがって、HTML 側の PublishRequest、merged publish、latest keep / restore、archive 分離、R29 close 済みの URL state / 状態語彙 / レイアウト契約は再設計されていない。
- html_generation 側の unit test 23 passed は、少なくとも今回の `master_storage` 側変更が既存 publish semantics を破壊していない補助事実として扱える。

### 5.6 実行・検証の整合
- `./.venv/Scripts/python.exe -m pytest tests/unit/master_storage tests/unit/night_update -q` → 25 passed
- `./.venv/Scripts/python.exe -m pytest tests/unit/html_generation -q` → 23 passed
- 変更ファイル数は 5 であり、変更対象外ファイルへの波及は小さい。
- 今回共有された差分説明から、night_update / HTML の非再設計方針は守られている。

## 6. 今回受け入れた内容
今回受け入れたのは、前段で受け入れた最小実装の上に、completed schema・physical detail の decision close 内容を実装へ反映した範囲である。具体的には以下を受け入れる。

- header 系 table の supplemental 用に限定した `payload_json` の保持
- child / supporting table からの `payload_json` 排除
- logical row での `payload_json` 露出禁止
- `proposal_target` immutable
- `order_fill` append-only
- `holding_snapshot_position` の `snapshot_id` 単位確定集合
- `evidence_ref` の append / superseded 相当更新
- `evidence_ref` の header 系親行中心の親境界
- `position_cycle` / `us_virtual_watch` を `evidence_ref` 標準親対象へ含めない初版境界
- `change_set` の header 系中心 record-unit 解決
- 既存の night_update / HTML publish semantics を壊さない最小接続維持
- 上記を担保する unit test の追加・更新

## 7. 今回受け入れていないもの
今回の accept は以下を含まない。

- completed CREATE TABLE 文の全文確定
- index / trigger の確定
- migration 方式の確定
- `proposal_target` / `holding_snapshot_position` / `evidence_ref` の列語彙完成版
- `payload_json` の物理列名有無、JSON 構造、廃止時期の最終固定
- `evidence_ref` の role 語彙完成版
- evidence 実体取得方式の確定
- `us_virtual_watch_header` の evidence_ref 標準接続
- `us_virtual_watch_header` の formalization 実装完了を示す明示テスト
- HTML / CSS / JavaScript の再設計
- R29 close 済み論点の reopen

## 8. 残課題
残課題はある。ただし、今回の accept を否定する blocking issue ではない。

### 8.1 completed DDL / index / trigger / migration 未確定
- completed CREATE TABLE 文の全文
- index
- trigger
- migration 方式

これらは今回の受入範囲外であり、後続の技術詳細工程で扱うべきである。

### 8.2 legacy child / supporting payload_json schema の自動移行未対応
現在の実装は、legacy child / supporting `payload_json` schema を自動移行せず、検知時に明示エラーとする。これは silent migration を避ける点では妥当だが、既存ローカル DB に旧 schema が残っている場合は起動時に停止し得る。

### 8.3 typed 列語彙の completed 化未了
`proposal_target`、`holding_snapshot_position`、`evidence_ref` の typed 列は scaffold 最小化のための暫定であり、完成版語彙は未固定である。

### 8.4 evidence_ref の role / status 語彙未固定
今回の `evidence_ref` は append / superseded 相当更新を実装しているが、語彙自体は最終固定していない。completed DDL / migration 段階で再整理が必要である。

### 8.5 米国株 2 表の formalization 境界のうち `us_virtual_watch_header` 側の実証が弱い
`us_pilot_header` は change set / night update テストで「変化がある日だけ」対象になることが確認されている。一方で、`us_virtual_watch_header` については schema 対象に含まれていても、formalization 実装の明示テストまでは今回確認されていない。現時点では、schema 対象として保持しつつ、formalization 実証は residual として残る。

## 9. 仕様書修正要否
結論として、**今回の受入結果を理由にした追加の仕様書修正は不要** と判断する。

理由は以下のとおりである。

1. 反映済み仕様書はすでに `payload_json` の許容境界、child 更新粒度、`evidence_ref` の標準接続先、米国株 2 表の formalization 境界を fixed 済みである。
2. 今回の実装は、その反映済み仕様へ physical scaffold を寄せたものであり、新しい仕様決定を追加していない。
3. 今回残る論点は completed DDL、index、trigger、migration、語彙完成版などの技術詳細であり、仕様本文に未固定として残すべきものに属する。
4. したがって、今回必要なのは仕様書本文の再改版ではなく、受入メモとしての記録である。

## 10. 残課題管理表更新要否
原則として **不要** とする。

理由は以下のとおりである。

- 今回は `master_storage_completed_schema_and_physical_detail_decision_boundary` を実装側で受け入れた記録であり、新規 open issue を追加する性質ではない。
- 反映済み仕様と管理表ドラフトの方向性に対し、今回の実装は整合側である。
- 残るものは新規論点ではなく、completed DDL、migration、語彙完成版、`us_virtual_watch_header` 実証補強などの residual である。

ただし、後続で completed DDL、migration、`evidence_ref` 語彙完成版、米国株 2 表 formalization 完成を独立工程として扱う場合は、その時点で必要最小限の open issue 化を検討してよい。

## 11. 第三者目線の最終点検
第三者目線で再点検した結果、以下を確認した。

- 前段受入メモの内容と、今回の追加受入内容が混線せずに分離されている
- accept の根拠と accept していない範囲が分離されている
- `payload_json`、child 更新粒度、`evidence_ref`、米国株 2 表という今回の主論点が明示的に回収されている
- residual を accept 理由へ混ぜていない
- R29 close 済み範囲への逆流を受入根拠に含めていない
- HTML 側を未変更にした理由が「未着手」ではなく「責務境界維持」として整理されている
- `us_virtual_watch_header` 側の実証不足を曖昧にせず residual として残している
- 完成版 DDL / migration 未確定を accept 理由へ混ぜていない
- 要約しすぎて child 更新粒度の table 別差分が落ちていない

現時点で、受入メモとして致命的な漏れ、要約過多による曖昧化、責務混線は見当たらない。

## 12. 結論
正本保存基盤・夜更新正式化導線に対する今回の completed schema・physical detail 実装は、**accept（残課題付き）** とする。

今回の accept は、前段で受け入れた最小実装を、反映済み仕様の decision close 内容へ寄せたものである。したがって、現時点では追加の仕様書改版や新規 open issue 追加は不要であり、本受入メモの更新保存をもって十分と判断する。
