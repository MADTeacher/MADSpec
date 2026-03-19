from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .constants import DEFAULT_EMBEDDING_DIMENSION
from .text import _matches_scope, _snippet, _sql_escape, _tokenize

try:
    import lancedb
    import pyarrow as pa
except ImportError:  # pragma: no cover - exercised only before dependency install
    lancedb = None
    pa = None


class EmbeddingProvider:
    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimension
            weight = 1.0 + (digest[1] / 255.0)
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class VectorMemoryIndex:
    def __init__(self, root_dir: Path, *, provider: EmbeddingProvider | None = None) -> None:
        self.root_dir = root_dir
        self.provider = provider or EmbeddingProvider()
        self.backend_name = "lancedb" if lancedb is not None and pa is not None else "manifest"

    def ensure_layout(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.backend_name == "lancedb":
            db = self._connection()
            existing_raw = db.list_tables() if hasattr(db, "list_tables") else db.table_names()
            existing = set(getattr(existing_raw, "tables", existing_raw))
            for name in ("memory_chunks", "artifact_chunks"):
                if name not in existing:
                    db.create_table(name, schema=self._schema())
            return
        for name in ("memory_chunks.jsonl", "artifact_chunks.jsonl"):
            path = self.root_dir / name
            if not path.exists():
                path.write_text("", encoding="utf-8")

    def upsert_chunks(self, table_name: str, chunks: list[dict[str, Any]]) -> None:
        self.ensure_layout()
        if self.backend_name == "lancedb":
            table = self._open_table(table_name)
            source_filters = {
                (str(item["source_type"]), str(item["source_id"]))
                for item in chunks
            }
            if source_filters:
                predicate = " OR ".join(
                    f"(source_type = '{_sql_escape(source_type)}' AND source_id = '{_sql_escape(source_id)}')"
                    for source_type, source_id in sorted(source_filters)
                )
                table.delete(predicate)
            rows = [self._lancedb_row(item) for item in chunks]
            if rows:
                table.add(rows)
            return
        path = self._table_path(table_name)
        existing = {item["chunk_id"]: item for item in self._read_chunks(path)}
        source_keys = {
            (item["source_type"], item["source_id"])
            for item in chunks
        }
        for chunk_id, item in list(existing.items()):
            if (item.get("source_type"), item.get("source_id")) in source_keys:
                existing.pop(chunk_id, None)
        for item in chunks:
            existing[item["chunk_id"]] = item
        rows = sorted(existing.values(), key=lambda item: item["chunk_id"])
        self._write_chunks(path, rows)

    def search(
        self,
        query: str,
        *,
        branch: str,
        stage: str | None = None,
        step_id: str | None = None,
        scope: str = "branch",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self.ensure_layout()
        query_vector = self.provider.embed_text(query)
        if self.backend_name == "lancedb":
            scored: list[dict[str, Any]] = []
            for table_name in ("memory_chunks", "artifact_chunks"):
                table = self._open_table(table_name)
                query_builder = table.search(query_vector)
                predicate = _lancedb_filter(
                    branch=branch,
                    stage=stage,
                    step_id=step_id,
                    scope=scope,
                )
                if predicate:
                    query_builder = query_builder.where(predicate, prefilter=True)
                rows = query_builder.limit(limit * 2).to_list()
                for row in rows:
                    distance = float(row.get("_distance", 0.0))
                    score = 1.0 / (1.0 + distance)
                    scored.append(
                        {
                            "chunk_id": row["chunk_id"],
                            "source_type": row["source_type"],
                            "source_id": row["source_id"],
                            "branch": row.get("branch"),
                            "stage": row.get("stage"),
                            "step_id": row.get("step_id"),
                            "scope": row.get("scope"),
                            "status": row.get("status"),
                            "kind": row.get("kind"),
                            "content_hash": row.get("content_hash"),
                            "snippet": row.get("snippet"),
                            "text": row.get("text"),
                            "score": round(score, 6),
                        }
                    )
            scored.sort(key=lambda item: item["score"], reverse=True)
            return scored[:limit]
        rows = self._read_chunks(self._table_path("memory_chunks"))
        rows.extend(self._read_chunks(self._table_path("artifact_chunks")))
        scoped_rows = [
            row
            for row in rows
            if _matches_scope(
                row_branch=row.get("branch"),
                row_stage=row.get("stage"),
                row_step_id=row.get("step_id"),
                branch=branch,
                stage=stage,
                step_id=step_id,
                scope=scope,
            )
        ]
        scored: list[dict[str, Any]] = []
        for row in scoped_rows:
            score = _cosine_similarity(query_vector, row.get("vector", []))
            if score <= 0:
                continue
            scored.append({**row, "score": round(score, 6)})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def list_tables(self) -> list[str]:
        if not self.root_dir.exists():
            return []
        if self.backend_name == "lancedb":
            db = self._connection()
            existing_raw = db.list_tables() if hasattr(db, "list_tables") else db.table_names()
            return sorted(getattr(existing_raw, "tables", existing_raw))
        tables: list[str] = []
        if (self.root_dir / "memory_chunks.jsonl").exists():
            tables.append("memory_chunks")
        if (self.root_dir / "artifact_chunks.jsonl").exists():
            tables.append("artifact_chunks")
        return tables

    def count_chunks(self, table_name: str) -> int:
        if not self.root_dir.exists():
            return 0
        if self.backend_name == "lancedb":
            if table_name not in set(self.list_tables()):
                return 0
            table = self._open_table(table_name)
            if hasattr(table, "count_rows"):
                return int(table.count_rows())
            return len(table.to_list())
        return len(self._read_chunks(self._table_path(table_name)))

    def count_source_chunks(self, table_name: str, *, source_type: str, source_id: str) -> int:
        if not self.root_dir.exists():
            return 0
        if self.backend_name == "lancedb":
            if table_name not in set(self.list_tables()):
                return 0
            table = self._open_table(table_name)
            rows = table.to_arrow().to_pylist()
            return len(
                [
                    row
                    for row in rows
                    if row.get("source_type") == source_type and row.get("source_id") == source_id
                ]
            )
        return len(
            [
                row
                for row in self._read_chunks(self._table_path(table_name))
                if row.get("source_type") == source_type and row.get("source_id") == source_id
            ]
        )

    def describe(self) -> dict[str, Any]:
        tables = self.list_tables()
        files = []
        if self.root_dir.exists():
            files = [
                str(path.relative_to(self.root_dir))
                for path in sorted(self.root_dir.iterdir())
                if path.is_file()
            ]
        return {
            "backend": self.backend_name,
            "root_dir_exists": self.root_dir.exists(),
            "tables": [
                {"name": table_name, "rows": self.count_chunks(table_name)}
                for table_name in tables
            ],
            "files": files,
        }

    def _table_path(self, table_name: str) -> Path:
        filename = "artifact_chunks.jsonl" if table_name == "artifact_chunks" else "memory_chunks.jsonl"
        return self.root_dir / filename

    def _connection(self):
        if lancedb is None or pa is None:
            raise RuntimeError("lancedb dependency is not installed")
        return lancedb.connect(str(self.root_dir))

    def _schema(self):
        assert pa is not None
        return pa.schema(
            [
                pa.field("chunk_id", pa.string()),
                pa.field("source_type", pa.string()),
                pa.field("source_id", pa.string()),
                pa.field("branch", pa.string()),
                pa.field("stage", pa.string()),
                pa.field("step_id", pa.string()),
                pa.field("scope", pa.string()),
                pa.field("status", pa.string()),
                pa.field("kind", pa.string()),
                pa.field("content_hash", pa.string()),
                pa.field("text", pa.string()),
                pa.field("snippet", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), self.provider.dimension)),
            ]
        )

    def _open_table(self, table_name: str):
        db = self._connection()
        try:
            return db.open_table(table_name)
        except Exception:
            return db.create_table(table_name, schema=self._schema())

    def _lancedb_row(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_id": item["chunk_id"],
            "source_type": item["source_type"],
            "source_id": item["source_id"],
            "branch": item["branch"],
            "stage": item.get("stage"),
            "step_id": item.get("step_id"),
            "scope": item.get("scope") or "branch",
            "status": item.get("status") or "validated",
            "kind": item.get("kind") or item["source_type"],
            "content_hash": item["content_hash"],
            "text": item["text"],
            "snippet": item["snippet"],
            "vector": [float(value) for value in item["vector"]],
        }

    def _read_chunks(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return rows

    def _write_chunks(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )


def _chunk_source_text(
    *,
    source_type: str,
    source_id: str,
    branch: str,
    stage: str | None,
    step_id: str | None,
    scope: str | None,
    status: str | None,
    kind: str | None,
    content_hash: str,
    text: str,
    provider: EmbeddingProvider,
    table_name: str,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    normalized_text = text.strip()
    if not normalized_text:
        return chunks
    parts = [part.strip() for part in normalized_text.split("\n\n") if part.strip()]
    if not parts:
        parts = [normalized_text]
    buffer = ""
    index = 0
    for part in parts:
        candidate = f"{buffer}\n\n{part}".strip() if buffer else part
        if len(candidate) > 500 and buffer:
            chunks.append(
                _chunk_row(
                    table_name=table_name,
                    source_type=source_type,
                    source_id=source_id,
                    branch=branch,
                    stage=stage,
                    step_id=step_id,
                    scope=scope,
                    status=status,
                    kind=kind,
                    content_hash=content_hash,
                    text=buffer,
                    provider=provider,
                    index=index,
                )
            )
            index += 1
            buffer = part
        else:
            buffer = candidate
    if buffer:
        chunks.append(
            _chunk_row(
                table_name=table_name,
                source_type=source_type,
                source_id=source_id,
                branch=branch,
                stage=stage,
                step_id=step_id,
                scope=scope,
                status=status,
                kind=kind,
                content_hash=content_hash,
                text=buffer,
                provider=provider,
                index=index,
            )
        )
    return chunks


def _chunk_row(
    *,
    table_name: str,
    source_type: str,
    source_id: str,
    branch: str,
    stage: str | None,
    step_id: str | None,
    scope: str | None,
    status: str | None,
    kind: str | None,
    content_hash: str,
    text: str,
    provider: EmbeddingProvider,
    index: int,
) -> dict[str, Any]:
    return {
        "table_name": table_name,
        "chunk_id": f"{source_type}:{source_id}:{index}",
        "source_type": source_type,
        "source_id": source_id,
        "branch": branch,
        "stage": stage,
        "step_id": step_id,
        "scope": scope or "branch",
        "status": status or "validated",
        "kind": kind or source_type,
        "content_hash": content_hash,
        "text": text,
        "snippet": _snippet(text),
        "vector": provider.embed_text(text),
    }


def _lancedb_filter(*, branch: str, stage: str | None, step_id: str | None, scope: str) -> str | None:
    filters = []
    if scope != "project":
        filters.append(f"branch = '{_sql_escape(branch)}'")
    if scope in {"stage", "step"} and stage:
        filters.append(f"stage = '{_sql_escape(stage)}'")
    if scope == "step" and step_id:
        filters.append(f"step_id = '{_sql_escape(step_id)}'")
    return " AND ".join(filters) if filters else None


def _cosine_similarity(lhs: list[float], rhs: Iterable[float]) -> float:
    rhs_list = list(rhs)
    if not lhs or not rhs_list or len(lhs) != len(rhs_list):
        return 0.0
    dot = sum(a * b for a, b in zip(lhs, rhs_list))
    lhs_norm = math.sqrt(sum(value * value for value in lhs))
    rhs_norm = math.sqrt(sum(value * value for value in rhs_list))
    if lhs_norm == 0 or rhs_norm == 0:
        return 0.0
    return dot / (lhs_norm * rhs_norm)
