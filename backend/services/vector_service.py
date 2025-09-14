import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger(__name__)


class VectorService:
    """Chroma-based vector store for report text, using all-MiniLM-L6-v2 embeddings.

    This service is optional and degrades gracefully if dependencies are missing.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("VECTOR_DB_ENABLED", "1") != "0"
        self._client = None
        self._collection = None

        if not self.enabled:
            logger.info("VectorService disabled via VECTOR_DB_ENABLED=0")
            return

        try:
            # Try to disable Chroma telemetry proactively
            os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
            os.environ.setdefault("POSTHOG_DISABLED", "true")

            import chromadb  # type: ignore
            from chromadb.utils import embedding_functions  # type: ignore
            try:
                from chromadb.config import Settings  # type: ignore
                settings = Settings(anonymized_telemetry=False)
            except Exception:
                settings = None

            persist_dir = (Path(__file__).resolve().parent.parent / "vectorstore").resolve()
            persist_dir.mkdir(parents=True, exist_ok=True)

            # Silence telemetry loggers in case env/settings are ignored
            for name in [
                "chromadb.telemetry",
                "chromadb.telemetry.product",
                "chromadb.telemetry.product.posthog",
            ]:
                try:
                    logging.getLogger(name).disabled = True
                except Exception:
                    pass

            # Initialize client
            if settings is not None:
                try:
                    self._client = chromadb.PersistentClient(path=str(persist_dir), settings=settings)
                except TypeError:
                    # Older API without settings param
                    self._client = chromadb.PersistentClient(path=str(persist_dir))
            else:
                self._client = chromadb.PersistentClient(path=str(persist_dir))
            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            # cosine is default for SentenceTransformer embeddings
            self._collection = self._client.get_or_create_collection(
                name="reports",
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("VectorService initialized with Chroma at %s", persist_dir)
        except Exception as e:
            self.enabled = False
            logger.warning("VectorService disabled (init error): %s", str(e))

    def add_document(self, patient_id: Optional[str], text: str, filename: Optional[str] = None) -> Optional[str]:
        if not self.enabled or not self._collection:
            return None
        try:
            doc_id = str(uuid4())
            metadata = {
                "patient_id": patient_id or "unknown",
                "filename": filename or "unknown",
                "timestamp": datetime.utcnow().isoformat(),
                "chunk_index": 0,
                "num_chunks": 1,
            }
            self._collection.add(documents=[text], metadatas=[metadata], ids=[doc_id])
            return doc_id
        except Exception as e:
            logger.error("VectorService.add_document error: %s", str(e))
            return None

    def add_document_chunks(
        self,
        patient_id: Optional[str],
        text: str,
        filename: Optional[str] = None,
        chunk_size: int = 800,
        overlap: int = 200,
    ) -> List[str]:
        if not self.enabled or not self._collection:
            return []
        chunks = self._chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            return []
        timestamp = datetime.utcnow().isoformat()
        ids: List[str] = []
        try:
            for idx, chunk in enumerate(chunks):
                doc_id = f"{uuid4()}"
                metadata = {
                    "patient_id": patient_id or "unknown",
                    "filename": filename or "unknown",
                    "timestamp": timestamp,
                    "chunk_index": idx,
                    "num_chunks": len(chunks),
                }
                self._collection.add(documents=[chunk], metadatas=[metadata], ids=[doc_id])
                ids.append(doc_id)
            return ids
        except Exception as e:
            logger.error("VectorService.add_document_chunks error: %s", str(e))
            return ids

    def list_texts_by_patient(self, patient_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        if not self.enabled or not self._collection:
            return []
        try:
            result = self._collection.get(where={"patient_id": patient_id}, limit=limit, include=["documents", "metadatas", "ids"])
            docs = result.get("documents", []) or []
            metas = result.get("metadatas", []) or []
            ids = result.get("ids", []) or []
            items: List[Dict[str, Any]] = []
            for i in range(min(len(docs), len(metas), len(ids))):
                items.append({"id": ids[i], "text": docs[i], "metadata": metas[i]})
            # Sort by timestamp if available, then by chunk index
            def sort_key(x: Dict[str, Any]):
                ts = x.get("metadata", {}).get("timestamp") or ""
                idx = x.get("metadata", {}).get("chunk_index") or 0
                return (ts, idx)
            items.sort(key=sort_key)
            return items
        except Exception as e:
            logger.error("VectorService.list_texts_by_patient error: %s", str(e))
            return []

    def query_similar(self, patient_id: Optional[str], text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self.enabled or not self._collection:
            return []
        try:
            where = {"patient_id": patient_id} if patient_id else {}
            result = self._collection.query(query_texts=[text], n_results=top_k, where=where)
            docs = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0] if "distances" in result else []
            out: List[Dict[str, Any]] = []
            for i, doc in enumerate(docs):
                out.append({
                    "text": doc,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                })
            return out
        except Exception as e:
            logger.error("VectorService.query_similar error: %s", str(e))
            return []

    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
        if not text:
            return []
        text = text.strip()
        if len(text) <= chunk_size:
            return [text]
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - overlap
            if start < 0:
                start = 0
        return chunks


