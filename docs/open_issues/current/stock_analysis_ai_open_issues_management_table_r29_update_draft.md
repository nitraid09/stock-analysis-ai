# 株式分析AI 残課題管理表 更新ドラフト（R29反映用）

- 文書名: 株式分析AI 残課題管理表 更新ドラフト（R29反映用）
- 位置づけ: 現行の残課題管理表へマージするための更新案
- 注意: 本ファイルは、R29 系論点の decision 結果および仕様本文反映完了後の close 更新差分を独立文書として整理したものである。既存管理表の他行は省略している。

---

## 1. 更新対象

- target_issue_id: R29_html_implementation_pipeline_and_output_contract
- related_issue_id:
  - R29-O01 HTML出力単位と画面ファイル分割規約
  - R29-O02 generated_html latest / generations / archive の責務分離
  - R29-O03 再生成ジョブの入力境界・失敗時扱い・回復方針
  - R29-O04 URL / path / query / hash の論理方針と stable key 深リンク接続
  - R29-O05 評価系列切替、絞込、並び替え、画面状態保持の方針
  - R29-O06 空状態、未記録、対象外、エラー状態、再生成失敗時の表示契約
  - R29-O07 PC前提レイアウト詳細、スクロール境界、breakpoint 固定要否
  - R29-O08 実装へ委譲する技術方式と仕様で固定する項目の最終境界
  - R29-O09 今回閉じる粒度と実装着手前の最小残件化

## 2. ステータス更新案

### 2.1 親論点

- issue_id: R29_html_implementation_pipeline_and_output_contract
- phase: open_issue_resolution
- status_before: open
- status_after_decision: decision_close_reflection_pending
- status_after_reflection: closed
- planned_reflection_specs:
  - 株式分析AI プロジェクト目的・運用初版仕様書
  - 必要時: 株式分析AI 残課題管理表
- management_table_action: 親論点は本文反映完了をもって closed とし、新規 open issue は追加しない

### 2.2 子論点別更新案

#### R29-O01 HTML出力単位と画面ファイル分割規約
- status: close
- final_decision: HTML出力単位は原則として1標準画面1公開HTMLファイルとし、提案詳細は `proposal_id` 単位、月次レビューは月次キー単位のファイル群化を許容する
- reflection_target:
  - 第15章 記録および振り返り
  - 第19章 初版結論
- keep_open_reason: なし

#### R29-O02 generated_html latest / generations / archive の責務分離
- status: close
- final_decision: `generated_html\generations` は generation 単位の staging / publish 履歴領域、`generated_html\latest` は last successful publish、`archive\monthly` は successful generation 由来の月次凍結参照として分離する
- reflection_target:
  - 第15章 記録および振り返り
  - 第19章 初版結論
- keep_open_reason: なし

#### R29-O03 再生成ジョブの入力境界・失敗時扱い・回復方針
- status: close
- final_decision: 再生成ジョブは change set、generation 識別子、表示条件、publish mode を最小入力とし、storage / orchestration / render の責務を分離する。再生成失敗時は latest を維持し、運用ログ記録と後続再生成で回復する
- reflection_target:
  - 第15章 記録および振り返り
- keep_open_reason: なし

#### R29-O04 URL / path / query / hash の論理方針と stable key 深リンク接続
- status: close
- final_decision: path は画面責務または自然な個別参照単位、query は共有すべき閲覧状態、hash は同一ページ内の stable key ジャンプとして扱う
- reflection_target:
  - 第15章 記録および振り返り
- keep_open_reason: なし

#### R29-O05 評価系列切替、絞込、並び替え、画面状態保持の方針
- status: close
- final_decision: 評価系列切替、絞込、並び替え、対象期間切替等は原則として URL query で再現可能な共有状態とし、アコーディオン開閉、列幅、一時ハイライト等の画面内一時状態は正式URL契約へ含めない
- reflection_target:
  - 第15章 記録および振り返り
  - 第19章 初版結論
- keep_open_reason: なし

#### R29-O06 空状態、未記録、対象外、エラー状態、再生成失敗時の表示契約
- status: close
- final_decision: `empty`、`none`、`not_applicable`、未記録、評価対象外、参照不能、再生成失敗、エラー状態の意味を分離固定し、同一表示へ潰さない
- reflection_target:
  - 第15章 記録および振り返り
  - 第19章 初版結論
- keep_open_reason: なし

#### R29-O07 PC前提レイアウト詳細、スクロール境界、breakpoint 固定要否
- status: close
- final_decision: PC前提とし、主縦スクロール1本、上部共通ヘッダおよび一覧画面の絞込・並び替え帯の sticky 表示許容、表の横 overflow の component 内閉込めを最低契約として固定し、breakpoint 実数値は実装へ委譲する
- reflection_target:
  - 第15章 記録および振り返り
  - 第19章 初版結論
- keep_open_reason: なし

#### R29-O08 実装へ委譲する技術方式と仕様で固定する項目の最終境界
- status: close
- final_decision: publish semantics、出力単位、URL状態責務、状態語彙、PC前提レイアウト制約、最低受入条件は仕様で固定し、HTML / CSS / JavaScript 実装コード、フレームワーク、色、breakpoint 実数値、ルーティング方式、SQL / API / cache 技術方式は実装へ委譲する
- reflection_target:
  - 第15章 記録および振り返り
  - 第17章 運用上の注意
- keep_open_reason: なし

#### R29-O09 今回閉じる粒度と実装着手前の最小残件化
- status: close
- final_decision: R29 は HTML実装前の出力契約と再生成パイプライン境界の確定をもって close とし、新規 open issue は追加しない。次段は reflection 後の実装工程へ接続する
- reflection_target:
  - 第18章 残課題
- keep_open_reason: なし

## 3. 管理表への追記文案

以下の要旨を既存の管理表へ反映する。

- R29 は decision 段階で substantive close とし、reflection 反映後に closed とする
- O01〜O09 はすべて close とする
- 新規 open issue は追加しない
- 反映対象は主として第15章、第17章、第18章、第19章とする
- 次工程は仕様書差し替え後の HTML / CSS / JavaScript 実装工程へ接続する

## 4. 本更新後の扱い

- 本件は、新規 open issue を増やさない
- 仕様本文へ反映済みであれば、R29 系論点は管理表上も closed としてよい
- 今後の派生論点は、HTML / CSS / JavaScript 実装コード、フレームワーク、breakpoint 実数値、ルーティング技術方式等の実装方式に限って別論点化する
