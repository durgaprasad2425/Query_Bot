import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from app.core.config import get_settings
from app.models.model import DocumentChunking

settings = get_settings()


class VectorStore:
    """
    Manages the ChromaDB instance for storing and retrieving document embeddings.
    Provides methods to add text sequences and query by embedding distance.
    """
    def __init__(self) -> None:
        self._emb = OpenAIEmbeddings(model=settings.openai_embedding_model, openai_api_key=settings.openai_api_key)
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir, settings=ChromaSettings(anonymized_telemetry=False))
        self._col = self._client.get_or_create_collection(name=settings.chroma_collection_name, metadata={"hnsw:space": "cosine"})

    def insert_documents(self, chunks: list[DocumentChunking]) -> None:
        """
        Embeds and stores the given document chunks into the underlying vector database.
        """
        if not chunks: return
        texts = [c.content for c in chunks]
        self._col.add(ids=[c.chunk_id for c in chunks], embeddings=self._emb.embed_documents(texts), documents=texts, metadatas=[c.metadata for c in chunks])

    def query_embeddings(self, query: str, top_k: int) -> list[dict]:
        """
        Performs a dense similarity search using OpenAI embeddings and returns the nearest neighbors.
        """
        if self._col.count() == 0: return []
        res = self._col.query(query_embeddings=[self._emb.embed_query(query)], n_results=min(top_k, self._col.count()), include=["documents", "metadatas", "distances"])
        return [{"content": d, "metadata": m, "score": 1.0 - dist} for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]

    def fetch_all_records(self) -> list[dict]:
        """
        Retrieves all documents currently stored in the database, mostly used for BM25 re-indexing.
        """
        if self._col.count() == 0: return []
        r = self._col.get(include=["documents", "metadatas"])
        return [{"content": d, "metadata": m} for d, m in zip(r["documents"], r["metadatas"])]

    @property
    def record_count(self) -> int: 
        """Returns the total number of chunks preserved in the vectors."""
        return self._col.count()
