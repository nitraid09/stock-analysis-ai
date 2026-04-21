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
            generation_status="publish_failed",
            publish_status="publish_failed",
            archive_status="not_attempted",
            restore_status="restored",
            failure_reason="simulated failure",
        )
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["master_update_status"] == "success"
    assert payload["generation_status"] == "publish_failed"
    assert payload["publish_status"] == "publish_failed"
    assert payload["restore_status"] == "restored"
    assert payload["generation_id"] == "gen-log"
