"""Contracts for the SQLite-centered master storage boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from stock_analysis_ai.html_generation.exceptions import ContractError

TableRole = Literal["parent", "child", "supporting"]

REQUIRED_TABLES: tuple[str, ...] = (
    "proposal_header",
    "proposal_target",
    "order_header",
    "order_fill",
    "holding_snapshot_header",
    "holding_snapshot_position",
    "review_header",
    "position_cycle_registry",
    "evidence_ref",
)
OPTIONAL_TABLES: tuple[str, ...] = (
    "us_virtual_watch_header",
    "us_pilot_header",
)
ALL_TABLES: tuple[str, ...] = REQUIRED_TABLES + OPTIONAL_TABLES

PARENT_TABLES: tuple[str, ...] = (
    "proposal_header",
    "order_header",
    "holding_snapshot_header",
    "review_header",
    "us_virtual_watch_header",
    "us_pilot_header",
)
CHILD_TABLES: tuple[str, ...] = (
    "proposal_target",
    "order_fill",
    "holding_snapshot_position",
)
SUPPORTING_TABLES: tuple[str, ...] = (
    "position_cycle_registry",
    "evidence_ref",
)

PRIMARY_STABLE_KEYS: tuple[str, ...] = (
    "proposal_id",
    "order_id",
    "position_cycle_id",
    "snapshot_id",
    "review_id",
)
RESERVATION_ONLY_KEYS: tuple[str, ...] = (
    "us_virtual_watch_id",
    "us_pilot_id",
)
ALL_KEY_NAMES: tuple[str, ...] = PRIMARY_STABLE_KEYS + RESERVATION_ONLY_KEYS

RECONCILIATION_STATUSES: tuple[str, ...] = (
    "unreconciled",
    "reconciled",
    "evidence_replaced",
)
REVIEW_PRIMARY_SUBJECT_TYPES: tuple[str, ...] = (
    "proposal",
    "position_cycle",
    "period",
)
EVIDENCE_PARENT_TYPES: tuple[str, ...] = (
    "proposal",
    "order",
    "holding_snapshot",
    "review",
    "us_pilot",
)


@dataclass(frozen=True)
class TableContract:
    """Physical table boundary fixed by the v0.22 schema contract."""

    table_name: str
    role: TableRole
    stable_key_fields: tuple[str, ...] = ()
    parent_key_field: str | None = None


TABLE_CONTRACTS: dict[str, TableContract] = {
    "proposal_header": TableContract(
        table_name="proposal_header",
        role="parent",
        stable_key_fields=("proposal_id",),
    ),
    "proposal_target": TableContract(
        table_name="proposal_target",
        role="child",
        parent_key_field="proposal_id",
    ),
    "order_header": TableContract(
        table_name="order_header",
        role="parent",
        stable_key_fields=("order_id",),
    ),
    "order_fill": TableContract(
        table_name="order_fill",
        role="child",
        parent_key_field="order_id",
    ),
    "holding_snapshot_header": TableContract(
        table_name="holding_snapshot_header",
        role="parent",
        stable_key_fields=("snapshot_id",),
    ),
    "holding_snapshot_position": TableContract(
        table_name="holding_snapshot_position",
        role="child",
        parent_key_field="snapshot_id",
    ),
    "review_header": TableContract(
        table_name="review_header",
        role="parent",
        stable_key_fields=("review_id",),
    ),
    "position_cycle_registry": TableContract(
        table_name="position_cycle_registry",
        role="supporting",
        stable_key_fields=("position_cycle_id",),
    ),
    "evidence_ref": TableContract(
        table_name="evidence_ref",
        role="supporting",
    ),
    "us_virtual_watch_header": TableContract(
        table_name="us_virtual_watch_header",
        role="parent",
        stable_key_fields=("us_virtual_watch_id",),
    ),
    "us_pilot_header": TableContract(
        table_name="us_pilot_header",
        role="parent",
        stable_key_fields=("us_pilot_id",),
    ),
}

STABLE_KEY_FIELDS_BY_TABLE: dict[str, tuple[str, ...]] = {
    table_name: contract.stable_key_fields
    for table_name, contract in TABLE_CONTRACTS.items()
    if contract.stable_key_fields
}
CHILD_PARENT_FIELDS: dict[str, str] = {
    table_name: contract.parent_key_field
    for table_name, contract in TABLE_CONTRACTS.items()
    if contract.parent_key_field is not None
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ensure_non_blank(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class MasterStoragePaths:
    """Filesystem layout for the SQLite-centered master storage."""

    project_root: Path

    @property
    def storage_root(self) -> Path:
        return self.project_root / "master" / "storage"

    @property
    def sqlite_file(self) -> Path:
        return self.storage_root / "master_storage.sqlite3"


@dataclass(frozen=True)
class ReviewPrimarySubject:
    """Single primary subject attached to a review row."""

    subject_type: str
    subject_id: str

    def __post_init__(self) -> None:
        if self.subject_type not in REVIEW_PRIMARY_SUBJECT_TYPES:
            raise ContractError(f"Unsupported review primary subject type: {self.subject_type}")
        _ensure_non_blank(self.subject_id, "subject_id")

    def to_dict(self) -> dict[str, str]:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ReviewPrimarySubject":
        return cls(
            subject_type=_ensure_non_blank(payload.get("subject_type"), "subject_type"),
            subject_id=_ensure_non_blank(payload.get("subject_id"), "subject_id"),
        )


@dataclass(frozen=True)
class EvidenceParent:
    """Single-parent contract for evidence references."""

    parent_type: str
    parent_id: str

    def __post_init__(self) -> None:
        if self.parent_type not in EVIDENCE_PARENT_TYPES:
            raise ContractError(f"Unsupported evidence parent type: {self.parent_type}")
        _ensure_non_blank(self.parent_id, "parent_id")

    def to_dict(self) -> dict[str, str]:
        return {
            "parent_type": self.parent_type,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EvidenceParent":
        return cls(
            parent_type=_ensure_non_blank(payload.get("parent_type"), "parent_type"),
            parent_id=_ensure_non_blank(payload.get("parent_id"), "parent_id"),
        )


@dataclass(frozen=True)
class MasterStorageSnapshot:
    """Logical snapshot materialized from the SQLite master storage."""

    tables: dict[str, tuple[dict[str, Any], ...]] = field(default_factory=dict)
    storage_engine: str = "sqlite"
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.storage_engine != "sqlite":
            raise ContractError("master storage snapshots must come from the SQLite-centered storage boundary.")
        object.__setattr__(self, "updated_at", ensure_aware_datetime(self.updated_at))
        normalize_table_inventory(self.tables)
        normalized_tables = {
            table_name: tuple(dict(row) for row in self.tables[table_name])
            for table_name in ALL_TABLES
        }
        object.__setattr__(self, "tables", normalized_tables)

    @classmethod
    def empty(cls) -> "MasterStorageSnapshot":
        return cls(tables={table_name: () for table_name in ALL_TABLES})

    def to_mutable_tables(self) -> dict[str, list[dict[str, Any]]]:
        return {
            table_name: [dict(row) for row in rows]
            for table_name, rows in self.tables.items()
        }


class MasterStorageTransactionContract(Protocol):
    """Transaction boundary for atomic master storage replacement."""

    def load_snapshot(self) -> MasterStorageSnapshot:
        """Load the current logical snapshot within the open transaction."""

    def replace_snapshot(self, snapshot: MasterStorageSnapshot) -> None:
        """Replace the persisted snapshot contents atomically."""


class MasterStorageRepositoryContract(Protocol):
    """Repository boundary above the SQLite adapter."""

    def transaction(self) -> MasterStorageTransactionContract:
        """Open a transaction boundary over the SQLite master store."""


def normalize_table_inventory(tables: Mapping[str, Any]) -> None:
    missing = [table_name for table_name in ALL_TABLES if table_name not in tables]
    unexpected = [table_name for table_name in tables if table_name not in ALL_TABLES]
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing tables: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected tables: {', '.join(unexpected)}")
        raise ContractError("; ".join(details))
    for table_name in ALL_TABLES:
        rows = tables[table_name]
        if not isinstance(rows, (list, tuple)):
            raise ContractError(f"{table_name} must contain an ordered row collection.")


def _collect_ids(rows: tuple[dict[str, Any], ...], field_name: str) -> set[str]:
    values: set[str] = set()
    for row in rows:
        value = row.get(field_name)
        if isinstance(value, str) and value.strip():
            values.add(value)
    return values


def _validate_unique_stable_keys(
    rows: tuple[dict[str, Any], ...],
    fields: tuple[str, ...],
    table_name: str,
) -> None:
    if not fields:
        return
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(_ensure_non_blank(row.get(field_name), field_name) for field_name in fields)
        if key in seen:
            raise ContractError(f"{table_name} contains duplicate stable key {key}.")
        seen.add(key)


def _validate_review_rows(rows: tuple[dict[str, Any], ...]) -> None:
    for row in rows:
        _ensure_non_blank(row.get("review_id"), "review_id")
        primary_subject = row.get("primary_subject")
        if not isinstance(primary_subject, Mapping):
            raise ContractError("review_header rows must contain primary_subject.")
        ReviewPrimarySubject.from_mapping(primary_subject)


def _validate_reference_path(value: Any) -> str:
    reference_path = _ensure_non_blank(value, "reference_path")
    if reference_path.startswith(("/", "\\")) or (len(reference_path) > 1 and reference_path[1] == ":"):
        raise ContractError("reference_path must use a project-relative path contract.")
    return reference_path


def _validate_evidence_rows(rows: tuple[dict[str, Any], ...]) -> None:
    for row in rows:
        parent = row.get("parent")
        if not isinstance(parent, Mapping):
            raise ContractError("evidence_ref rows must contain a single parent mapping.")
        EvidenceParent.from_mapping(parent)
        _validate_reference_path(row.get("reference_path"))


def validate_master_storage_snapshot(snapshot: MasterStorageSnapshot) -> None:
    normalize_table_inventory(snapshot.tables)
    for table_name, rows in snapshot.tables.items():
        for row in rows:
            if "payload_json" in row:
                raise ContractError(
                    f"{table_name} must not expose payload_json as a logical row field."
                )
    for table_name, fields in STABLE_KEY_FIELDS_BY_TABLE.items():
        _validate_unique_stable_keys(snapshot.tables[table_name], fields, table_name)

    proposal_ids = _collect_ids(snapshot.tables["proposal_header"], "proposal_id")
    order_ids = _collect_ids(snapshot.tables["order_header"], "order_id")
    snapshot_ids = _collect_ids(snapshot.tables["holding_snapshot_header"], "snapshot_id")
    review_ids = _collect_ids(snapshot.tables["review_header"], "review_id")
    position_cycle_ids = _collect_ids(snapshot.tables["position_cycle_registry"], "position_cycle_id")
    us_pilot_ids = _collect_ids(snapshot.tables["us_pilot_header"], "us_pilot_id")

    for row in snapshot.tables["proposal_header"]:
        _ensure_non_blank(row.get("proposal_id"), "proposal_id")
    for row in snapshot.tables["proposal_target"]:
        proposal_id = _ensure_non_blank(row.get("proposal_id"), "proposal_id")
        if proposal_id not in proposal_ids:
            raise ContractError(f"proposal_target references unknown proposal_id: {proposal_id}")
    for row in snapshot.tables["order_header"]:
        _ensure_non_blank(row.get("order_id"), "order_id")
        _ensure_non_blank(row.get("order_status"), "order_status")
        reconciliation_status = _ensure_non_blank(row.get("reconciliation_status"), "reconciliation_status")
        if reconciliation_status not in RECONCILIATION_STATUSES:
            raise ContractError(f"Unsupported reconciliation_status: {reconciliation_status}")
        proposal_id = row.get("proposal_id")
        if proposal_id and proposal_id not in proposal_ids:
            raise ContractError(f"order_header references unknown proposal_id: {proposal_id}")
        position_cycle_id = row.get("position_cycle_id")
        if position_cycle_id and position_cycle_id not in position_cycle_ids:
            raise ContractError(
                f"order_header references unknown position_cycle_id: {position_cycle_id}"
            )
    for row in snapshot.tables["order_fill"]:
        order_id = _ensure_non_blank(row.get("order_id"), "order_id")
        if order_id not in order_ids:
            raise ContractError(f"order_fill references unknown order_id: {order_id}")
        position_cycle_id = row.get("position_cycle_id")
        if position_cycle_id and position_cycle_id not in position_cycle_ids:
            raise ContractError(f"order_fill references unknown position_cycle_id: {position_cycle_id}")
    for row in snapshot.tables["holding_snapshot_header"]:
        _ensure_non_blank(row.get("snapshot_id"), "snapshot_id")
    for row in snapshot.tables["holding_snapshot_position"]:
        snapshot_id = _ensure_non_blank(row.get("snapshot_id"), "snapshot_id")
        if snapshot_id not in snapshot_ids:
            raise ContractError(
                f"holding_snapshot_position references unknown snapshot_id: {snapshot_id}"
            )

    _validate_review_rows(snapshot.tables["review_header"])
    for row in snapshot.tables["review_header"]:
        primary_subject = ReviewPrimarySubject.from_mapping(row["primary_subject"])
        if primary_subject.subject_type == "proposal" and primary_subject.subject_id not in proposal_ids:
            raise ContractError(
                f"review_header references unknown proposal primary subject: {primary_subject.subject_id}"
            )
        if (
            primary_subject.subject_type == "position_cycle"
            and primary_subject.subject_id not in position_cycle_ids
        ):
            raise ContractError(
                "review_header references unknown position_cycle primary subject: "
                f"{primary_subject.subject_id}"
            )

    for row in snapshot.tables["position_cycle_registry"]:
        _ensure_non_blank(row.get("position_cycle_id"), "position_cycle_id")

    _validate_evidence_rows(snapshot.tables["evidence_ref"])
    for row in snapshot.tables["evidence_ref"]:
        parent = EvidenceParent.from_mapping(row["parent"])
        if parent.parent_type == "proposal" and parent.parent_id not in proposal_ids:
            raise ContractError(f"evidence_ref references unknown proposal parent: {parent.parent_id}")
        if parent.parent_type == "order" and parent.parent_id not in order_ids:
            raise ContractError(f"evidence_ref references unknown order parent: {parent.parent_id}")
        if parent.parent_type == "holding_snapshot" and parent.parent_id not in snapshot_ids:
            raise ContractError(
                "evidence_ref references unknown holding_snapshot parent: "
                f"{parent.parent_id}"
            )
        if parent.parent_type == "review" and parent.parent_id not in review_ids:
            raise ContractError(f"evidence_ref references unknown review parent: {parent.parent_id}")
        if parent.parent_type == "us_pilot" and parent.parent_id not in us_pilot_ids:
            raise ContractError(f"evidence_ref references unknown us_pilot parent: {parent.parent_id}")


def scan_reserved_key_counters(snapshot: MasterStorageSnapshot) -> dict[str, int]:
    counters = {key_name: 0 for key_name in ALL_KEY_NAMES}
    for rows in snapshot.tables.values():
        for row in rows:
            for key_name in ALL_KEY_NAMES:
                value = row.get(key_name)
                if not isinstance(value, str) or "-" not in value:
                    continue
                suffix = value.rsplit("-", 1)[-1]
                if suffix.isdigit():
                    counters[key_name] = max(counters[key_name], int(suffix))
    return counters


__all__ = [
    "ALL_KEY_NAMES",
    "ALL_TABLES",
    "CHILD_PARENT_FIELDS",
    "CHILD_TABLES",
    "EVIDENCE_PARENT_TYPES",
    "EvidenceParent",
    "MasterStoragePaths",
    "MasterStorageRepositoryContract",
    "MasterStorageSnapshot",
    "MasterStorageTransactionContract",
    "OPTIONAL_TABLES",
    "PARENT_TABLES",
    "PRIMARY_STABLE_KEYS",
    "RECONCILIATION_STATUSES",
    "REQUIRED_TABLES",
    "RESERVATION_ONLY_KEYS",
    "REVIEW_PRIMARY_SUBJECT_TYPES",
    "ReviewPrimarySubject",
    "STABLE_KEY_FIELDS_BY_TABLE",
    "SUPPORTING_TABLES",
    "TABLE_CONTRACTS",
    "TableContract",
    "TableRole",
    "ensure_aware_datetime",
    "scan_reserved_key_counters",
    "utc_now",
    "validate_master_storage_snapshot",
]
