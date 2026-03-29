from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable

from ...domain.conflicts import PROJECT_MEMORY_BRANCH
from .constants import DEFAULT_EMBEDDING_DIMENSION
from .embedding_registry import EmbeddingModelSpec
from .text import _matches_scope, _snippet, _sql_escape, _tokenize

try:
    import lancedb
    import pyarrow as pa
except ImportError:  # pragma: no cover - exercised only before dependency install
    lancedb = None
    pa = None


class BaseEmbeddingProvider(ABC):
    def __init__(self, *, provider_kind: str, model_key: str | None, dimension: int) -> None:
        self.provider_kind = provider_kind
        self.model_key = model_key
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        return self.embed_passage(text)

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def embed_passage(self, text: str) -> list[float]:
        raise NotImplementedError


class HashEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIMENSION) -> None:
        super().__init__(provider_kind="hash", model_key="default", dimension=dimension)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_passage(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimension
            weight = 1.0 + (digest[1] / 255.0)
            vector[index] += weight
        return _normalize_vector(vector)


class LocalHfOnnxEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(
        self,
        *,
        model_spec: EmbeddingModelSpec,
        local_path: Path,
        max_length: int = 512,
        tokenizer_path: Path | None = None,
        model_path: Path | None = None,
        tokenizer: Any | None = None,
        session: Any | None = None,
        numpy_module: Any | None = None,
    ) -> None:
        super().__init__(
            provider_kind=model_spec.provider_kind,
            model_key=model_spec.model_key,
            dimension=model_spec.dimension,
        )
        self.model_spec = model_spec
        self.local_path = local_path.resolve()
        self.max_length = max_length
        self.tokenizer_path = tokenizer_path
        self.model_path = model_path
        self._tokenizer = tokenizer
        self._session = session
        self._np = numpy_module

        if not self.local_path.exists():
            raise RuntimeError(f"Local model path does not exist: {self.local_path}")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, prefix=self.model_spec.query_prefix)

    def embed_passage(self, text: str) -> list[float]:
        return self._embed(text, prefix=self.model_spec.passage_prefix)

    def _embed(self, text: str, *, prefix: str) -> list[float]:
        normalized = text.strip()
        if not normalized:
            return _zero_vector(self.dimension)
        prompt = f"{prefix}{normalized}" if prefix else normalized
        outputs, attention_mask = self._run_model(prompt)
        vector = self._coerce_output_vector(outputs, attention_mask)
        if len(vector) != self.dimension:
            raise RuntimeError(
                f"Embedding dimension mismatch for model '{self.model_key}': "
                f"expected {self.dimension}, got {len(vector)}"
            )
        return vector

    def _run_model(self, prompt: str) -> tuple[Any, list[int]]:
        tokenizer, session = self._ensure_runtime()
        encoding = tokenizer.encode(prompt)
        session_inputs = list(session.get_inputs())
        if not session_inputs:
            raise RuntimeError(f"ONNX session for model '{self.model_key}' does not expose inputs.")

        target_length = _resolve_sequence_length(
            session_inputs=session_inputs,
            token_count=len(getattr(encoding, "ids", []) or []),
            fallback=self.max_length,
        )
        input_ids = _truncate_and_pad(getattr(encoding, "ids", []), target_length)
        attention_mask = _truncate_and_pad(
            getattr(encoding, "attention_mask", []) or [1] * len(input_ids),
            target_length,
        )
        token_type_ids = _truncate_and_pad(getattr(encoding, "type_ids", []) or [0] * len(input_ids), target_length)
        feed = self._build_feed_dict(
            session_inputs=session_inputs,
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        return session.run(None, feed), attention_mask

    def _build_feed_dict(
        self,
        *,
        session_inputs: list[Any],
        input_ids: list[int],
        attention_mask: list[int],
        token_type_ids: list[int],
    ) -> dict[str, Any]:
        names = [str(item.name) for item in session_inputs if getattr(item, "name", None)]
        if not names:
            raise RuntimeError(f"ONNX session for model '{self.model_key}' does not expose named inputs.")

        feed: dict[str, Any] = {}
        primary_name = names[0]
        tensors = {
            "input_ids": self._to_int_tensor(input_ids),
            "attention_mask": self._to_int_tensor(attention_mask),
            "token_type_ids": self._to_int_tensor(token_type_ids),
        }
        for key, value in tensors.items():
            if key in names:
                feed[key] = value
        if primary_name not in feed:
            feed[primary_name] = tensors["input_ids"]
        return feed

    def _to_int_tensor(self, values: list[int]) -> Any:
        if self._np is None:
            return [values]
        return self._np.asarray([values], dtype=self._np.int64)

    def _coerce_output_vector(self, outputs: Any, attention_mask: list[int]) -> list[float]:
        if not isinstance(outputs, (list, tuple)) or not outputs:
            raise RuntimeError(f"ONNX runtime returned no outputs for model '{self.model_key}'.")

        payload = _to_python(outputs[0])
        if not payload:
            return _zero_vector(self.dimension)

        if _is_3d(payload):
            return _mean_pool(payload[0], attention_mask, self.dimension)
        if _is_2d(payload):
            matrix = payload
            if len(matrix) == len(attention_mask):
                return _mean_pool(matrix, attention_mask, self.dimension)
            return _normalize_vector(_as_float_list(matrix[0]))
        if _is_1d(payload):
            return _normalize_vector(_as_float_list(payload))
        raise RuntimeError(f"Unsupported ONNX output shape for model '{self.model_key}'.")

    def _ensure_runtime(self) -> tuple[Any, Any]:
        needs_runtime_imports = self._tokenizer is None or self._session is None
        if self._tokenizer is None:
            self._tokenizer = self._load_tokenizer()
        if self._session is None:
            self._session = self._load_session()
        if self._np is None and needs_runtime_imports:
            self._np = self._load_numpy()
        return self._tokenizer, self._session

    def _load_tokenizer(self) -> Any:
        try:
            from tokenizers import Tokenizer
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "tokenizers is not installed; install project dependencies before using dense local embeddings."
            ) from exc

        tokenizer_path = self.tokenizer_path or _resolve_local_asset(
            self.local_path,
            preferred=("tokenizer.json",),
            suffix=".json",
        )
        if tokenizer_path is None:
            raise RuntimeError(
                f"Tokenizer assets not found for model '{self.model_key}' under {self.local_path}"
            )
        return Tokenizer.from_file(str(tokenizer_path))

    def _load_session(self) -> Any:
        try:
            import onnxruntime
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "onnxruntime is not installed; install project dependencies before using dense local embeddings."
            ) from exc

        model_path = self.model_path or _resolve_local_asset(
            self.local_path,
            preferred=("model.onnx", "onnx/model.onnx"),
            suffix=".onnx",
        )
        if model_path is None:
            raise RuntimeError(
                f"ONNX model assets not found for model '{self.model_key}' under {self.local_path}"
            )
        return onnxruntime.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

    def _load_numpy(self) -> Any:
        try:
            import numpy
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "numpy is not installed; install project dependencies before using dense local embeddings."
            ) from exc
        return numpy


EmbeddingProvider = HashEmbeddingProvider


class VectorMemoryIndex:
    def __init__(
        self,
        root_dir: Path,
        *,
        provider: BaseEmbeddingProvider | None = None,
        provider_kind: str | None = None,
        model_key: str | None = None,
        revision: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self.root_dir = root_dir
        resolved_dimension = dimension or (provider.dimension if provider is not None else DEFAULT_EMBEDDING_DIMENSION)
        self.provider = provider or HashEmbeddingProvider(dimension=resolved_dimension)
        self.provider_kind = provider_kind or self.provider.provider_kind
        self.model_key = model_key or self.provider.model_key or "default"
        self.revision = revision or "current"
        self.dimension = resolved_dimension
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

    def clear_tables(self) -> None:
        self.ensure_layout()
        if self.backend_name == "lancedb":
            db = self._connection()
            existing_raw = db.list_tables() if hasattr(db, "list_tables") else db.table_names()
            existing = set(getattr(existing_raw, "tables", existing_raw))
            for table_name in ("memory_chunks", "artifact_chunks"):
                if table_name in existing:
                    db.open_table(table_name).delete("1 = 1")
            return
        for table_name in ("memory_chunks", "artifact_chunks"):
            self._write_chunks(self._table_path(table_name), [])

    def delete_source_chunks(self, table_name: str, *, source_type: str, source_ids: list[str]) -> None:
        if not source_ids:
            return
        self.ensure_layout()
        normalized_ids = sorted({str(item) for item in source_ids if str(item)})
        if not normalized_ids:
            return
        if self.backend_name == "lancedb":
            table = self._open_table(table_name)
            predicate = " OR ".join(
                f"(source_type = '{_sql_escape(source_type)}' AND source_id = '{_sql_escape(source_id)}')"
                for source_id in normalized_ids
            )
            table.delete(predicate)
            return
        path = self._table_path(table_name)
        remaining = [
            item
            for item in self._read_chunks(path)
            if not (
                item.get("source_type") == source_type
                and str(item.get("source_id") or "") in normalized_ids
            )
        ]
        self._write_chunks(path, remaining)

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
        query_vector = self.provider.embed_query(query)
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

    def list_chunk_sources(self, table_name: str, *, source_type: str | None = None) -> list[dict[str, Any]]:
        if not self.root_dir.exists():
            return []
        if self.backend_name == "lancedb":
            if table_name not in set(self.list_tables()):
                return []
            rows = self._open_table(table_name).to_arrow().to_pylist()
        else:
            rows = self._read_chunks(self._table_path(table_name))
        unique: dict[tuple[str, ...], dict[str, Any]] = {}
        for row in rows:
            if source_type is not None and row.get("source_type") != source_type:
                continue
            key = (
                str(row.get("source_type") or ""),
                str(row.get("source_id") or ""),
                str(row.get("branch") or ""),
                str(row.get("stage") or ""),
                str(row.get("step_id") or ""),
                str(row.get("scope") or ""),
                str(row.get("status") or ""),
                str(row.get("kind") or ""),
            )
            if key in unique:
                continue
            unique[key] = {
                "source_type": row.get("source_type"),
                "source_id": row.get("source_id"),
                "branch": row.get("branch"),
                "stage": row.get("stage"),
                "step_id": row.get("step_id"),
                "scope": row.get("scope"),
                "status": row.get("status"),
                "kind": row.get("kind"),
            }
        return sorted(
            unique.values(),
            key=lambda item: (
                str(item.get("source_type") or ""),
                str(item.get("source_id") or ""),
                str(item.get("branch") or ""),
                str(item.get("scope") or ""),
                str(item.get("kind") or ""),
            ),
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
            "provider_kind": self.provider_kind,
            "model_key": self.model_key,
            "revision": self.revision,
            "dimension": self.dimension,
            "namespace_path": str(self.root_dir),
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
                pa.field("vector", pa.list_(pa.float32(), self.dimension)),
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
    provider: BaseEmbeddingProvider,
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
    provider: BaseEmbeddingProvider,
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
        "vector": provider.embed_passage(text),
    }


def _resolve_local_asset(
    root: Path,
    *,
    preferred: tuple[str, ...],
    suffix: str,
) -> Path | None:
    for relative in preferred:
        candidate = root / relative
        if candidate.exists():
            return candidate
    matches = sorted(path for path in root.rglob(f"*{suffix}") if path.is_file())
    return matches[0] if matches else None


def _resolve_sequence_length(*, session_inputs: list[Any], token_count: int, fallback: int) -> int:
    for input_meta in session_inputs:
        shape = getattr(input_meta, "shape", None)
        if isinstance(shape, (list, tuple)) and len(shape) >= 2:
            candidate = shape[1]
            if isinstance(candidate, int) and candidate > 0:
                return min(candidate, fallback)
    return max(1, min(token_count or 1, fallback))


def _truncate_and_pad(values: Iterable[int], target_length: int, *, pad_value: int = 0) -> list[int]:
    result = [int(value) for value in list(values)[:target_length]]
    if len(result) < target_length:
        result.extend([pad_value] * (target_length - len(result)))
    return result


def _to_python(value: Any) -> Any:
    return value.tolist() if hasattr(value, "tolist") else value


def _is_1d(value: Any) -> bool:
    return isinstance(value, list) and (not value or not isinstance(value[0], list))


def _is_2d(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and isinstance(value[0], list) and (
        not value[0] or not isinstance(value[0][0], list)
    )


def _is_3d(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and isinstance(value[0], list) and bool(value[0]) and isinstance(
        value[0][0], list
    )


def _as_float_list(values: Iterable[Any]) -> list[float]:
    return [float(item) for item in values]


def _mean_pool(sequence: list[list[Any]], attention_mask: list[int], dimension: int) -> list[float]:
    if not sequence:
        return _zero_vector(dimension)
    pooled = [0.0] * len(sequence[0])
    count = 0
    for index, token_vector in enumerate(sequence):
        if index >= len(attention_mask) or not attention_mask[index]:
            continue
        values = _as_float_list(token_vector)
        if len(values) != len(pooled):
            raise RuntimeError("Inconsistent ONNX token embedding width encountered during mean pooling.")
        pooled = [current + value for current, value in zip(pooled, values)]
        count += 1
    if count == 0:
        return _zero_vector(dimension)
    return _normalize_vector([value / count for value in pooled])


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _zero_vector(dimension: int) -> list[float]:
    return [0.0] * dimension


def _lancedb_filter(*, branch: str, stage: str | None, step_id: str | None, scope: str) -> str | None:
    filters = []
    if scope == "project":
        filters.append(f"branch = '{_sql_escape(PROJECT_MEMORY_BRANCH)}'")
    else:
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
