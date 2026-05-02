from functools import lru_cache
from app.agents.rag import RAGAgent
from app.knowledge_base.retriever import HybridRetriever
from app.knowledge_base.vector_store import VectorStore
from app.validators.response_validator import ResponseValidator


@lru_cache(maxsize=1)
def init_vector_database() -> VectorStore: return VectorStore()

@lru_cache(maxsize=1)
def init_document_retriever() -> HybridRetriever:
    r = HybridRetriever(init_vector_database()); r.recalculate_bm25_index(); return r

@lru_cache(maxsize=1)
def init_rag_agent() -> RAGAgent: return RAGAgent(init_document_retriever())

@lru_cache(maxsize=1)
def init_response_validator() -> ResponseValidator: return ResponseValidator()
