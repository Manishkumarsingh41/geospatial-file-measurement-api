"""Lightweight JSON-file-backed repository for file metadata.

This avoids the need for an external database while providing persistence
across application restarts.  The repository stores a single ``index.json``
inside the configured upload directory and organises per-file artefacts
under ``<upload_dir>/<file_id>/``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class FileRecord:
    """Metadata about a processed geospatial file."""

    id: str
    filename: str
    stored_path: str
    feature_count: int
    crs: str | None
    status: str
    created_at: str


class FileRepository:
    """Thread-safe (single-process) in-memory index backed by ``index.json``."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self._records: dict[str, FileRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Read the on-disk index into memory."""
        if not self.index_path.exists():
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            self._records = {k: FileRecord(**v) for k, v in data.items()}
        except (json.JSONDecodeError, TypeError):
            # Corrupt index — start fresh.
            self._records = {}

    def _persist(self) -> None:
        """Write the in-memory index to disk."""
        self.index_path.write_text(
            json.dumps(
                {k: asdict(v) for k, v in self._records.items()}, indent=2
            ),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, record: FileRecord) -> None:
        """Add or update a record and persist."""
        self._records[record.id] = record
        self._persist()

    def get(self, file_id: str) -> FileRecord | None:
        """Return a record by ID, or ``None`` if not found."""
        return self._records.get(file_id)

    def list_all(self) -> list[FileRecord]:
        """Return all stored records."""
        return list(self._records.values())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def now_iso() -> str:
        """Return the current UTC time in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()
