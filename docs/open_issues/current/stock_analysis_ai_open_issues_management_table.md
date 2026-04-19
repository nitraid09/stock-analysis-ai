# 株式分析AI 残課題管理表 更新ドラフト（正本保存基盤 completed schema・physical detail 反映用）

- 文書名: 株式分析AI 残課題管理表 更新ドラフト（正本保存基盤 completed schema・physical detail 反映用）
- 位置づけ: 現行の残課題管理表へマージするための更新案
- 注意: 本ファイルは、正本保存基盤の completed schema・physical detail 残課題レビュー結果を、既存管理表へ反映するための更新案である。既存管理表の他行は省略している。

---

## 1. 更新対象

- target_issue_id: master_storage_completed_schema_and_physical_detail_decision_boundary
- target_phase: 正本保存基盤 completed schema・physical detail 残課題の最小確定
- related_scope:
  - `payload_json` の許容境界
  - completed schema と completed DDL の固定境界
  - child 更新粒度の table 別固定
  - `evidence_ref` の order 系以外への運用拡張境界
  - `us_virtual_watch_header` / `us_pilot_header` の schema / 夜更新正式化境界

## 2. ステータス更新案

### 2.1 親論点

- issue_id: master_storage_completed_schema_and_physical_detail_decision_boundary
- phase: open_issue_resolution
- status_before: open
- status_after_decision: decision_close_reflection_pending
- status_after_reflection: closed
- planned_reflection_specs:
  - 株式分析AI プロジェクト目的・運用初版仕様書
- management_table_action: 新規 open issue は追加しない。本文反映完了をもって closed とする

### 2.2 決定要旨

- `payload_json` は、正式列契約の代替として扱わない
- `payload_json` を実装都合で残置する場合でも、header 系 table の補助情報に限定し、child 系 table および supporting table へ導入しない
- child 更新粒度は一律の親キー単位置換とせず、table 別に固定する
- `proposal_target` は immutable、`order_fill` は append-only、`holding_snapshot_position` は `snapshot_id` 単位の確定集合、`evidence_ref` は append または superseded 管理を原則とする
- `evidence_ref` の標準接続先は header 系親行を中心とし、`order_header` を標準対象、`holding_snapshot_header` と `us_pilot_header` を条件付き対象、`proposal_header` と `review_header` を任意対象とする
- `proposal_target`、`order_fill`、`holding_snapshot_position`、`position_cycle_registry` への `evidence_ref` 直付けは初版標準としない
- `us_virtual_watch_header` および `us_pilot_header` は completed schema の対象に含める
- 米国株2表の夜更新正式化は、当該記録に正式更新がある日を対象とし、日本株系と同一頻度の毎営業日必須を要求しない
- completed CREATE TABLE 文、index、trigger、migration、`payload_json` の物理列名有無、`evidence_ref` の role 語彙完成版、自動夜更新ジョブの技術詳細は本文固定しない

## 3. 管理表への追記文案

以下の要旨を既存の管理表へ反映する。

- `master_storage_completed_schema_and_physical_detail_decision_boundary` は decision close とし、本文反映完了後に closed とする
- 新規 open issue は追加しない
- 今回の反映対象は、`payload_json` 許容境界、child 更新粒度、`evidence_ref` 運用境界、米国株2表の schema / 夜更新正式化境界とする
- completed CREATE TABLE 文、index、trigger、migration、自動夜更新ジョブの技術詳細は、引き続き本文固定外の技術詳細として扱う

## 4. 本更新後の扱い

- 本件は、新規 open issue を増やさない
- 仕様本文へ反映済みであれば、本論点は管理表上も closed としてよい
- 今後の派生論点は、実装コード、DDL 完成版、index、trigger、migration、自動夜更新ジョブの技術方式に限定して別途扱う
