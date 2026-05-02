from __future__ import annotations
from collections import defaultdict
from rank_bm25 import BM25Okapi
from app.core.config import get_settings
from app.knowledge_base.vector_store import VectorStore

settings = get_settings()
_RRF_K = 60


class HybridRetriever:
    """
    Implements a hybrid retrieval strategy combining dense vector embeddings with sparse BM25 retrieval.
    Offers recalculation of BM25 based on the vector store corpus and a fusion strategy for reranking.
    """
    def __init__(self, vs: VectorStore) -> None:
        self._vs = vs
        self._bm25: BM25Okapi | None = None
        self._corpus: list[dict] = []

    def recalculate_bm25_index(self) -> None:
        """
        Reconstructs the BM25 search index using the latest snapshot from the vector store.
        Needed after ingesting new chunks.
        """
        self._corpus = self._vs.fetch_all_records()
        if self._corpus:
            self._bm25 = BM25Okapi([d["content"].lower().split() for d in self._corpus])

    def find_relevant_context(self, query: str) -> list[dict]:
        """
        Returns the top results using both dense similarity search and sparse BM25 term frequency.
        Applies reciprocal rank fusion (RRF) to combine results.
        """
        dense = self._vs.query_embeddings(query, top_k=settings.retrieval_top_k)
        if not self._bm25: return dense[:settings.hybrid_final_k]
        scores = self._bm25.get_scores(query.lower().split())
        sparse = [{"content": self._corpus[i]["content"], "metadata": self._corpus[i]["metadata"]}
                  for i in sorted(range(len(scores)), key=lambda x: scores[x], reverse=True)[:settings.bm25_top_k] if scores[i] > 0]
        return self._reciprocal_rank_fusion(dense, sparse)[:settings.hybrid_final_k]

    @staticmethod
    def _reciprocal_rank_fusion(dense, sparse):
        """
        Helper method to perform RRF, standardizing scores across different retrieval systems.
        """
        scores: dict[str, float] = defaultdict(float)
        store: dict[str, dict] = {}
        for rank, h in enumerate(dense, 1):
            scores[h["content"]] += 1 / (_RRF_K + rank); store[h["content"]] = h
        for rank, h in enumerate(sparse, 1):
            scores[h["content"]] += 1 / (_RRF_K + rank); store.setdefault(h["content"], h)
        return [store[k] for k, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]

    @property
    def contains_records(self) -> bool: 
        """Check if any documents exist in the vector store."""
        return self._vs.record_count > 0
