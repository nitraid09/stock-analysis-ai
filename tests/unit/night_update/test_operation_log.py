from __future__ import annotations

import json

from stock_analysis_ai.night_update.operation_log import OperationLogEntry, OperationLogRepository


def test_operation_log_records_required_status_fields(tmp_path) -> None:
    repository = OperationLogRepository(tmp_path)
    log_path = repository.append(
        OperationLogEntry(
            generation_id="gen-log",
            master_update_status="success",
            reconciliation_status_summary={"unreconciled": 1, "reconciled": 0, "evidence_replaced": 0},
            generation_status="failed",
            publish_status="failed",
            archive_status="not_requested",
            restore_status="kept_previous_latest",
            failure_reason="simulated failure",
        )
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["master_update_status"] == "success"
    assert payload["publish_status"] == "failed"
    assert payload["restore_status"] == "kept_previous_latest"
    assert payload["generation_id"] == "gen-log"
