import hashlib
import math
import re
from collections.abc import Sequence
from typing import ClassVar, Protocol
from uuid import UUID, uuid4

from .database import transaction
from .errors import TenantDenied
from .identity import fingerprint


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class DeterministicEmbedding:
    """Lexical hashing with an explicit tiny multilingual dictionary, not a semantic benchmark."""

    ALIASES: ClassVar[dict[str, str]] = {
        "refund": "refund",
        "refunds": "refund",
        "возврат": "refund",
        "возврата": "refund",
        "повернення": "refund",
        "поверненню": "refund",
        "policy": "policy",
        "политика": "policy",
        "політика": "policy",
        "days": "days",
        "дней": "days",
        "днів": "days",
        "quota": "quota",
        "квота": "quota",
        "limit": "quota",
        "ліміт": "quota",
        "security": "security",
        "безопасность": "security",
        "безпека": "security",
    }

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * 64
        for token in re.findall(r"\w+", text.casefold()):
            canonical = self.ALIASES.get(token, token)
            index = int.from_bytes(hashlib.sha256(canonical.encode()).digest()[:4], "big") % 64
            vector[index] += 1
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm else vector


def chunk_text(text: str, size: int = 400, overlap: int = 60) -> list[str]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("invalid chunk configuration")
    cleaned = text.replace("\r\n", "\n").strip()
    return [cleaned[start : start + size] for start in range(0, len(cleaned), size - overlap)]


def similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimension mismatch")
    return sum(a * b for a, b in zip(left, right, strict=True))


class RetrievalService:
    def __init__(self, dsn: str, embedding: EmbeddingProvider | None = None) -> None:
        self.dsn = dsn
        self.embedding = embedding or DeterministicEmbedding()

    async def upload(self, tenant: UUID, name: str, text: str) -> UUID:
        from .schemas import DocumentUpload

        validated = DocumentUpload(name=name, text=text)
        digest = fingerprint({"text": validated.text})
        async with transaction(self.dsn) as c:
            await c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1,0))", str(tenant) + digest
            )
            previous = await c.fetchval(
                "SELECT id FROM documents WHERE tenant_id=$1 AND content_hash=$2", tenant, digest
            )
            if previous:
                return UUID(str(previous))
            doc = uuid4()
            await c.execute(
                "INSERT INTO documents(tenant_id,id,name,media_type,content_hash,content) VALUES($1,$2,$3,'text/plain',$4,$5)",
                tenant,
                doc,
                validated.name,
                digest,
                validated.text,
            )
            for ordinal, chunk in enumerate(chunk_text(validated.text)):
                await c.execute(
                    "INSERT INTO chunks(tenant_id,id,document_id,ordinal,content,embedding) VALUES($1,$2,$3,$4,$5,$6)",
                    tenant,
                    uuid4(),
                    doc,
                    ordinal,
                    chunk,
                    self.embedding.embed(chunk),
                )
            return doc

    async def search(
        self, tenant: UUID, query: str, limit: int = 5, document: UUID | None = None
    ) -> list[dict[str, object]]:
        async with transaction(self.dsn) as c:
            if document and not await c.fetchval(
                "SELECT EXISTS(SELECT 1 FROM documents WHERE tenant_id=$1 AND id=$2)",
                tenant,
                document,
            ):
                raise TenantDenied("document unavailable")
            rows = await c.fetch(
                """SELECT c.id,c.document_id,c.content,c.embedding,d.name FROM chunks c
                   JOIN documents d ON d.tenant_id=c.tenant_id AND d.id=c.document_id
                   WHERE c.tenant_id=$1 AND ($2::uuid IS NULL OR c.document_id=$2)
                   ORDER BY c.document_id,c.ordinal LIMIT 2000""",
                tenant,
                document,
            )
        vector = self.embedding.embed(query)
        ranked = [
            {
                "chunk_id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "document_name": row["name"],
                "content": row["content"],
                "score": similarity(vector, row["embedding"]),
            }
            for row in rows
        ]
        ranked.sort(key=lambda hit: (-float(hit["score"]), str(hit["chunk_id"])))
        return ranked[:limit]
