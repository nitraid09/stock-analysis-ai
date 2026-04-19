from __future__ import annotations

import json
from pathlib import Path

from stock_analysis_ai.html_generation.cli import main


def test_cli_executes_publish(tmp_path: Path, capsys) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "change_set": ["proposal"],
                "shared": {},
                "screens": {
                    "top": {"sections": [{"id": "summary", "title": "上段全幅サマリ", "text": "summary"}]},
                    "proposal_list": {"sections": [{"id": "active", "title": "アクティブ", "text": "list"}]},
                    "proposal_detail": [{"proposal_id": "P-001", "sections": [{"id": "summary", "title": "提案サマリ", "text": "detail"}]}],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--payload",
            str(payload_path),
            "--generation-id",
            "gen-cli",
            "--publish-mode",
            "publish",
            "--output-root",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    result = json.loads(captured.out)
    assert result["published"] is True
    assert (tmp_path / "generated_html" / "latest" / "proposal_detail" / "P-001.html").exists()
