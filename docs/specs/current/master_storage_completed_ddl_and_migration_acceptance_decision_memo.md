# 正本保存基盤 completed DDL / migration 実装受入判定メモ

- 文書名: 正本保存基盤 completed DDL / migration 実装受入判定メモ
- 文書ID: master_storage_completed_ddl_and_migration_acceptance_decision_memo
- 作成日: 2026-04-19
- 対象論点ID: master_storage_completed_ddl_and_migration_decision_boundary
- 判定: accept
- close 判定: close 可
- 位置づけ: 正本保存基盤 completed DDL / required index / trigger / migration 実装について、現行仕様との整合および受入可否を記録する acceptance decision memo。本文仕様書の代替ではなく、実装受入判定の根拠整理に用いる。

---

## 1. 今回の目的

本メモは、正本保存基盤 completed DDL / required index / trigger / migration 実装について、現行の株式分析AIプロジェクト目的・運用仕様書で固定済みの decision boundary に整合するかを判定し、accept / close 可否を明示することを目的とする。

今回の対象は、以下に限定する。

- completed DDL 実装
- required index 実装
- trigger の扱い
- migration 実装
- repository / validator / helper / test による invariant enforcement
- 上記に関連する受入可否判定

今回の対象外は、以下とする。

- 仕様本文の新規確定事項追加
- HTML / CSS / JavaScript の再レビュー
- R29 close 済み事項の再検討
- completed schema / physical detail close 済み論点の再オープン
- open issues 本文更新
- migration CLI の追加設計
- typed vocabulary 完成版の固定
- evidence_ref role / status 完成語彙の固定
- us_virtual_watch_header formalization 実証完了判定

---

## 2. 判定結論

判定は **accept** とする。

close 判定は **close 可** とする。

今回のコード確認により、以前の summary-based 判定で residual として残っていた主要未確定は解消した。特に、relation 不整合の blocking failure、silent auto-migration 廃止、11表構成維持、payload_json 境界、table 別 invariant enforcement は、コード実体および unit test で確認できた。

一方で、pytest 実行ログそのものは本メモ作成時点では未添付である。ただし、これは今回の completed DDL / migration 実装受入の blocking とはしない。理由は、実装本体と unit test コードの双方から、受入条件の中核が既に確認できるためである。

---

## 3. 受入判定の根拠

### 3.1 11表構成の維持

受入可と判断する。

`contracts.py` では、required 9表と optional 2表を合わせた `ALL_TABLES` を 11表として固定している。`MasterStorageSnapshot.empty()` もこの11表を前提にしており、`test_contracts.py` でも `MasterStorageSnapshot` が exact eleven table boundaries を持つことを確認している。

したがって、新たな独立正本、集計専用正本、画面専用正本、latest/history 二重正本表は追加されていないと判断する。

### 3.2 payload_json 境界

受入可と判断する。

`schema.py` では、`payload_json` は header table のみに存在し、`proposal_target`、`order_fill`、`holding_snapshot_position`、`position_cycle_registry`、`evidence_ref` には physical column として存在しない。さらに `validate_master_storage_snapshot` は、logical row に `payload_json` が含まれている場合に失敗させる。

`test_contracts.py` でも child / supporting table に `payload_json` が存在しないことを確認している。

したがって、payload_json を header 補助用途に限定し、child / supporting へ逆流させない境界は維持されている。

### 3.3 stable key、親子 relation、状態列分離、evidence_ref 親境界

受入可と判断する。

`contracts.py` では、stable key 群、table contract、child-parent field、status vocabulary、evidence parent type を明示している。`schema.py` では、`order_status` と `reconciliation_status` を別列で保持し、`evidence_ref` 親 type を `proposal / order / holding_snapshot / review / us_pilot` に限定している。

`validate_master_storage_snapshot` は、child row が unknown parent を参照していないか、`review_header` の primary subject が単一か、`evidence_ref` が 1行1親系統になっているかを確認する。`test_reconciliation.py` でも `order_status` と `reconciliation_status` の分離が保持されている。

したがって、stable key、relation contract、状態列分離、evidence_ref 親境界は completed DDL / row contract に反映されている。

### 3.4 required index

受入可と判断する。

`schema.py` の `CREATE_INDEX_STATEMENTS` と `EXPECTED_INDEX_NAMES` により、以下に相当する index 群が実装されている。

- stable key / status lookup 補助
- header-child lookup 補助
- 注文照合支援
- evidence_ref 親判定支援
- change-set / publish 補助に必要な lookup

また `validate_completed_schema` は required index 欠落を失敗として扱う。

index SQL の列順や covering / partial の最終妥当性までは本文固定外であるが、今回の受入境界として要求される access pattern は満たしていると判断する。

### 3.5 trigger 未実装の扱い

受入可と判断する。

今回の schema 実装には trigger は含まれていない。一方、現行仕様は trigger を optional としており、採用する場合も defensive invariant 補助に限定し、business workflow を持たせてはならないとしている。

今回の実装では trigger を採用せず、repository / validator / test で invariant を担保している。trigger への workflow 逆流も発生していない。

したがって、trigger 未実装は不合格理由としない。

### 3.6 migration fail-fast、backup、verify、silent overwrite 禁止

受入可と判断する。

`migration.py` では、`preflight_master_storage`、`migrate_master_storage`、`verify_master_storage` が分離されている。legacy DB に対しては、backup 作成後、shadow DB へ materialize し、completed schema と snapshot load を通したうえで差し替えている。

また `MasterStorageRepository` / `SqliteMasterStorageAdapter` は legacy schema に対して silent auto-migration を行わず、明示 migrate を要求する。`test_migration.py` でも repository が legacy schema を explicit migration なしで読むことを拒否するテストがある。

したがって、migration は destructive overwrite を標準とせず、backup / preflight / verify / fail-fast / silent overwrite 禁止を満たしている。

### 3.7 relation 不整合 blocking failure

受入可と判断する。

以前の summary-based 判定では、この論点が close の主要阻害要因だった。今回のコード確認では、`validate_master_storage_snapshot` が unknown parent relation を失敗させ、`test_migration.py` に `test_preflight_detects_parent_relation_mismatch_in_legacy_rows` が存在する。

このテストは、存在しない `order_header` を参照する `order_fill` を legacy DB に置いた場合、preflight が `row_contract` の blocking issue を返すことを確認している。

したがって、relation 不整合は blocking failure として扱われていると判断する。

### 3.8 table 別 invariant enforcement

受入可と判断する。

`MasterStorageRepository.apply_table_changes()` は、table 別に処理を分岐している。

- `proposal_target`: immutable
- `order_fill`: append-only
- `holding_snapshot_position`: snapshot_id 単位確定集合
- `evidence_ref`: append / supersede

`test_contracts.py` でも、これらの invariant が違反時に `ContractError` となることを確認している。

したがって、spec で固定した child / supporting table 更新粒度は維持されている。

### 3.9 change-set 境界と workflow 逆流防止

受入可と判断する。

`change_set.py` は、table change から screen ではなく record unit を解決して `ChangeSet` を作る。`test_change_set.py` でも record-unit ベースの解決が確認されている。

今回の実装では change set 解決を DB trigger 側へ持たせておらず、workflow の DB 逆流も確認されない。

したがって、trigger への workflow 逆流禁止、および change-set 境界は守られている。

---

## 4. 今回受け入れる内容

今回受け入れる範囲は以下とする。

### 4.1 completed DDL

- 11表構成の physical schema
- header / child / supporting の責務分離
- order_status / reconciliation_status 分離
- proposal_status / position_status / review_scope_type / pilot_status の typed 列受け皿
- evidence_ref_id stable key
- evidence_ref 親 type 制約
- header-child FK
- payload_json の header 補助限定

### 4.2 required index

- stable key lookup 補助
- header-child lookup 補助
- 注文照合支援
- evidence_ref 親判定支援
- change-set / publish 補助に必要な最小 index 群

### 4.3 migration

- preflight
- backup
- shadow migrate
- verify
- silent overwrite 禁止
- explicit migrate 要求
- legacy evidence_ref stable key 補完
- relation mismatch を含む row contract blocking failure

### 4.4 invariant enforcement

- proposal_target immutable
- order_fill append-only
- holding_snapshot_position snapshot_id 単位確定集合
- evidence_ref append / supersede
- evidence_ref 1行1親系統
- review_header 単一 primary subject

### 4.5 helper / 補助実装

- stable key reservation
- position cycle assignment
- reconciliation evidence requirement
- record-unit change-set 解決

### 4.6 test

- contracts test
- migration test
- key factory test
- position cycle test
- reconciliation test
- change-set test

---

## 5. 今回受け入れていない内容

以下は今回の accept 範囲に含めない。

- pytest 実行ログそのものの確認
- completed CREATE TABLE 文の SQL 美観や将来最適化議論
- index の covering / partial 最適化議論
- migration CLI の追加設計
- typed vocabulary 完成版の固定
- evidence_ref role / status 完成語彙の固定
- us_virtual_watch_header formalization 実証完了判定
- HTML / publish semantics の再レビューそのもの

ただし、今回のコード確認範囲では、completed DDL / migration 実装受入を阻害する未完了は認めない。

---

## 6. residual の扱い

今回の受入論点を close するうえで、blocking residual はなしとする。

以下は、本文固定外または今回範囲外として残し得るが、本論点の close を阻害しない。

- evidence_ref role / status 完成語彙
- header payload 補助列以外の typed vocabulary 完成版
- migration CLI
- us_virtual_watch_header formalization 実証強化
- pytest 実行ログの別途保存

---

## 7. 現行仕様との整合

今回の accept 判定は、新規仕様を追加したものではない。現行仕様書に既に反映済みの decision boundary に対して、コード実体が整合していることを確認したものである。

特に以下の固定事項との整合を確認した。

- 11表構成
- 新規独立正本追加禁止
- payload_json の child / supporting 逆流禁止
- trigger optional、workflow 逆流禁止
- backup / preflight / verify / silent overwrite 禁止
- child / supporting table の table 別更新粒度
- evidence_ref 親境界

したがって、今回の結果をもって仕様本文へ新たな確定事項を追加する必要はない。

---

## 8. 仕様書反映要否

**不要** とする。

理由は、completed DDL / index / trigger / migration の decision boundary は、現行仕様本文へ既に反映済みであり、今回の作業はその実装受入判定だからである。

今回の accept / close は、本文追加ではなく acceptance decision memo 側で残すのが正しい。

---

## 9. open issues 管理表更新要否

**不要** とする。

current 台帳は active open issue なしであり、今回の accept / close に伴って新規未確定事項は増えていない。今回残るのは本文固定外または範囲外事項のみであり、新規 open issue 追加は不要と判断する。

---

## 10. close 判定

本論点 `master_storage_completed_ddl_and_migration_decision_boundary` は、**close 可** とする。

close 理由は以下のとおり。

- 11表、payload_json 境界、状態列分離、evidence_ref 親境界をコードで確認できた
- relation mismatch blocking failure を test で確認できた
- repository が silent auto-migration を行わず explicit migrate を要求することを確認できた
- table 別 invariant enforcement をコードと test で確認できた
- trigger 未実装は optional 範囲であり不合格理由とならない
- change-set / workflow 境界の逆流を認めない
- 新規 open issue を必要とする blocking が残っていない

---

## 11. 結論

今回送付されたコード確認結果に基づき、正本保存基盤 completed DDL / required index / trigger / migration 実装は、現行仕様の decision boundary に整合すると判断する。

したがって、判定は **accept**、close 判定は **close 可** とする。

本メモは acceptance decision memo として確定し、仕様書本文および current open issues 台帳の更新は行わない。
