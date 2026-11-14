import math
import uuid
from typing import Any

from sqlalchemy import Connection, Engine, bindparam, text
from sqlalchemy.orm import Session

from app.db.models import Document
from app.services.rag.source_policy import should_vectorize


class PgvectorNotReadyError(RuntimeError):
    pass


_TABLE_EXISTS = text("SELECT to_regclass('rag_document_vectors') IS NOT NULL")
_PROBE = text("""
    SELECT EXISTS (
        SELECT 1 FROM pg_catalog.pg_extension WHERE extname = 'vector'
    ) AS extension_installed,
    has_type_privilege(to_regtype('vector'), 'USAGE') AS vector_usable,
    to_regclass('documents') IS NOT NULL AS documents_exist,
    has_table_privilege(to_regclass('documents'), 'SELECT') AS can_read_documents,
    CASE WHEN to_regclass('rag_document_vectors') IS NULL THEN
        has_schema_privilege(current_schema(), 'CREATE')
        AND has_table_privilege(to_regclass('documents'), 'REFERENCES')
    ELSE
        has_table_privilege(to_regclass('rag_document_vectors'), 'SELECT')
        AND has_table_privilege(to_regclass('rag_document_vectors'), 'INSERT')
        AND has_table_privilege(to_regclass('rag_document_vectors'), 'UPDATE')
        AND has_table_privilege(to_regclass('rag_document_vectors'), 'DELETE')
    END AS can_manage_vectors
""")
_LOCK_SCHEMA = text("SELECT pg_advisory_xact_lock(893211569171826561)")
_CREATE_TABLE = text("""
    CREATE TABLE IF NOT EXISTS rag_document_vectors (
        collection_name TEXT NOT NULL,
        document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        embedding vector NOT NULL,
        PRIMARY KEY (collection_name, document_id)
    )
""")
_CREATE_DOCUMENT_INDEX = text("""
    CREATE INDEX IF NOT EXISTS ix_rag_document_vectors_document_id
    ON rag_document_vectors (document_id)
""")
_UPSERT = text("""
    INSERT INTO rag_document_vectors (collection_name, document_id, embedding)
    VALUES (:collection_name, :document_id, CAST(:embedding AS vector))
    ON CONFLICT (collection_name, document_id) DO UPDATE SET embedding = EXCLUDED.embedding
""")


def _uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


class PgvectorStore:
    def __init__(self, engine: Engine, collection_name: str, dimensions: int) -> None:
        self.engine = engine
        self.collection_name = collection_name
        self.dimensions = dimensions

    def _require_postgresql(self) -> None:
        if self.engine.dialect.name != "postgresql":
            raise PgvectorNotReadyError("pgvector 需要使用 PostgreSQL 作为应用数据库，请检查 DATABASE_URL。")

    def probe(self, *, db: Session | None = None) -> None:
        """Check readiness without creating the extension or any tables."""
        self._require_postgresql()
        if db is None:
            with self.engine.connect() as connection:
                self._probe(connection)
        else:
            self._probe(db)

    @staticmethod
    def _probe(connection: Connection | Session) -> None:
        row = connection.execute(_PROBE).mappings().one()
        if not row["extension_installed"]:
            raise PgvectorNotReadyError("当前 PostgreSQL 数据库未启用 pgvector，请在此数据库中执行 CREATE EXTENSION vector。")
        if not row["vector_usable"]:
            raise PgvectorNotReadyError("应用数据库用户无法访问 pgvector 类型，请检查扩展所在 schema、search_path 和使用权限。")
        if not row["documents_exist"]:
            raise PgvectorNotReadyError("当前 PostgreSQL 数据库尚未初始化 DevHarbor 文档表。")
        if not row["can_read_documents"] or not row["can_manage_vectors"]:
            raise PgvectorNotReadyError("应用数据库用户缺少创建或读写向量表的权限，请检查数据库授权。")

    def prepare_write(self, db: Session) -> None:
        """Prepare the vector table before a transaction changes its parent documents."""
        self._require_postgresql()
        if db.scalar(_TABLE_EXISTS):
            return
        self.probe(db=db)
        # Serialize first writes across processes. DDL commits or rolls back with the caller.
        db.execute(_LOCK_SCHEMA)
        if not db.scalar(_TABLE_EXISTS):
            db.execute(_CREATE_TABLE)
            db.execute(_CREATE_DOCUMENT_INDEX)

    def _vector_literal(self, vector: list[float]) -> str:
        if len(vector) != self.dimensions:
            raise ValueError(f"embedding has {len(vector)} dimensions; expected {self.dimensions}")
        if not all(math.isfinite(value) for value in vector) or not any(vector):
            raise ValueError("pgvector cosine search requires a finite, nonzero embedding")
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def upsert_documents(self, documents: list[Document], vectors: list[list[float]], *, db: Session) -> None:
        self._require_postgresql()
        if len(documents) != len(vectors):
            raise ValueError("document/vector count mismatch")
        rows = [
            {
                "collection_name": self.collection_name,
                "document_id": doc.id,
                "embedding": self._vector_literal(vector),
            }
            for doc, vector in zip(documents, vectors)
            if should_vectorize(doc.source_type)
        ]
        if rows:
            self.prepare_write(db)
            db.execute(_UPSERT, rows)

    def delete_documents(
        self,
        *,
        db: Session,
        repo_id: uuid.UUID | str | None = None,
        source_types: list[str] | None = None,
        source_id: uuid.UUID | str | None = None,
        document_ids: list[uuid.UUID | str] | None = None,
    ) -> None:
        self._require_postgresql()
        filters = []
        parameters: dict[str, Any] = {"collection_name": self.collection_name}
        bind_parameters = []
        if repo_id is not None:
            filters.append("d.repo_id = :repo_id")
            parameters["repo_id"] = _uuid(repo_id)
        if source_types:
            filters.append("d.source_type IN :source_types")
            parameters["source_types"] = source_types
            bind_parameters.append(bindparam("source_types", expanding=True))
        if source_id is not None:
            filters.append("d.source_id = :source_id")
            parameters["source_id"] = _uuid(source_id)
        if document_ids:
            filters.append("v.document_id IN :document_ids")
            parameters["document_ids"] = [_uuid(item) for item in document_ids]
            bind_parameters.append(bindparam("document_ids", expanding=True))
        if not filters or not db.scalar(_TABLE_EXISTS):
            return
        query = text("""
            DELETE FROM rag_document_vectors AS v USING documents AS d
            WHERE v.document_id = d.id AND v.collection_name = :collection_name AND
        """ + " AND ".join(filters)).bindparams(*bind_parameters)
        db.execute(query, parameters)

    def search(
        self,
        *,
        repo_id: uuid.UUID | str,
        query_embedding: list[float],
        source_type: str | None = None,
        source_types: list[str] | None = None,
        limit: int = 20,
        db: Session | None = None,
    ) -> list[dict[str, Any]]:
        self._require_postgresql()
        source_filter = [source_type] if source_type else source_types
        parameters: dict[str, Any] = {
            "collection_name": self.collection_name,
            "repo_id": _uuid(repo_id),
            "dimensions": self.dimensions,
            "query_embedding": self._vector_literal(query_embedding),
            "limit": limit,
        }
        source_clause = " AND d.source_type IN :source_types" if source_filter else ""
        query = text("""
            SELECT d.id, d.title, d.source_type, d.source_id, d.content, d.metadata,
                   1 - (v.embedding <=> CAST(:query_embedding AS vector)) AS score
            FROM rag_document_vectors AS v JOIN documents AS d ON d.id = v.document_id
            WHERE v.collection_name = :collection_name AND d.repo_id = :repo_id
                  AND vector_dims(v.embedding) = :dimensions
        """ + source_clause + " ORDER BY score DESC, d.id LIMIT :limit")
        if source_filter:
            parameters["source_types"] = source_filter
            query = query.bindparams(bindparam("source_types", expanding=True))
        if db is None:
            with self.engine.connect() as connection:
                rows = connection.execute(query, parameters).mappings().all() if connection.scalar(_TABLE_EXISTS) else []
        else:
            rows = db.execute(query, parameters).mappings().all() if db.scalar(_TABLE_EXISTS) else []
        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "source_type": row["source_type"],
                "source_id": str(row["source_id"]),
                "score": round(float(row["score"]), 4),
                "metadata": row["metadata"] or {},
                "snippet": row["content"][:260],
                "_raw_content": row["content"],
            }
            for row in rows
        ]
