from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PolicyChunk:
    source: str
    text: str
    score: float


class PolicyRetriever:
    """Small dependency-free policy retriever for local portfolio demos.

    In a production implementation, replace this with embeddings and a vector database
    such as pgvector, OpenSearch, Milvus, Pinecone, or ClickHouse vector search.
    """

    def __init__(self, policy_dir: Path):
        self.policy_dir = policy_dir
        self.documents = self._load_documents(policy_dir)

    def retrieve(self, query: str, top_k: int = 3) -> list[PolicyChunk]:
        query_tokens = self._tokenize(query)
        scored: list[PolicyChunk] = []

        for source, text in self.documents.items():
            for chunk in self._split_chunks(text):
                chunk_tokens = self._tokenize(chunk)
                if not chunk_tokens:
                    continue
                overlap = query_tokens.intersection(chunk_tokens)
                score = len(overlap) / max(len(query_tokens), 1)
                if score > 0:
                    scored.append(PolicyChunk(source=source, text=chunk.strip(), score=score))

        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    @staticmethod
    def _load_documents(policy_dir: Path) -> dict[str, str]:
        documents: dict[str, str] = {}
        if not policy_dir.exists():
            return documents

        for path in policy_dir.glob("*.md"):
            documents[path.name] = path.read_text(encoding="utf-8")
        return documents

    @staticmethod
    def _split_chunks(text: str) -> list[str]:
        chunks = re.split(r"\n\s*\n", text)
        return [chunk for chunk in chunks if chunk.strip()]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))
