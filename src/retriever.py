"""
Semantic retrieval using FAISS.
Supports K=1,3,5,10 and returns ranked chunks with similarity scores.
Interface: retrieve(query, k=5) -> List[Dict]
"""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import time

from .config import FAISS_INDEX_PATH, EMBEDDINGS_NPY_PATH, CHUNKS_JSONL, EMBEDDING_MODEL, DATA_PROCESSED_DIR
from .utils import load_jsonl, logger

class Retriever:
    def __init__(self, 
                 chunks_path: Path = CHUNKS_JSONL,
                 index_path: Path = FAISS_INDEX_PATH,
                 embeddings_path: Path = EMBEDDINGS_NPY_PATH,
                 embedding_model: str = EMBEDDING_MODEL):
        self.chunks_path = chunks_path
        self.index_path = index_path
        self.embeddings_path = embeddings_path
        self.embedding_model_name = embedding_model

        self.chunks = []
        self.index = None
        self.embedding_model = None
        self.model_type = None
        self.tfidf_vectorizer = None

        self._load()

    def _load(self):
        # Load chunks
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks not found: {self.chunks_path}")
        self.chunks = load_jsonl(self.chunks_path)
        logger.info(f"Loaded {len(self.chunks)} chunks")

        # Load FAISS index
        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {self.index_path}. Run embeddings first.")
        import faiss
        self.index = faiss.read_index(str(self.index_path))
        logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")

        # Determine embedding type
        meta_path = DATA_PROCESSED_DIR / "embedding_meta.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            self.model_type = meta.get("type", "sentence_transformer")
        else:
            # Heuristic: if tfidf vectorizer exists
            if (DATA_PROCESSED_DIR / "tfidf_vectorizer.pkl").exists():
                self.model_type = "tfidf"
            else:
                self.model_type = "sentence_transformer"

        # Load embedding model / vectorizer
        if self.model_type == "tfidf":
            vec_path = DATA_PROCESSED_DIR / "tfidf_vectorizer.pkl"
            if vec_path.exists():
                with open(vec_path, 'rb') as f:
                    self.tfidf_vectorizer = pickle.load(f)
                logger.info("Loaded TF-IDF vectorizer")
            else:
                raise FileNotFoundError("TF-IDF vectorizer not found but meta says tfidf")
        else:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model for queries: {self.embedding_model_name}")
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                logger.info("Embedding model loaded")
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer for retrieval: {e}, trying fallback")
                # Try tfidf fallback if available
                vec_path = DATA_PROCESSED_DIR / "tfidf_vectorizer.pkl"
                if vec_path.exists():
                    with open(vec_path, 'rb') as f:
                        self.tfidf_vectorizer = pickle.load(f)
                    self.model_type = "tfidf"
                    logger.info("Falling back to TF-IDF for query embedding")
                else:
                    raise

    def embed_query(self, query: str) -> np.ndarray:
        if self.model_type == "tfidf" and self.tfidf_vectorizer:
            vec = self.tfidf_vectorizer.transform([query]).toarray().astype(np.float32)
            # L2 normalize
            norm = np.linalg.norm(vec, axis=1, keepdims=True)
            norm = np.where(norm==0, 1, norm)
            vec = vec / norm
            return vec
        else:
            emb = self.embedding_model.encode([query], normalize_embeddings=True)
            return emb.astype(np.float32)

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        """Retrieve top-k chunks for query"""
        if not query.strip():
            return []
        
        start = time.perf_counter()
        q_emb = self.embed_query(query)
        retrieval_time_start = time.perf_counter()

        # FAISS search
        scores, indices = self.index.search(q_emb, k)
        retrieval_time = (time.perf_counter() - retrieval_time_start) * 1000  # ms

        results = []
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0]), start=1):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            results.append({
                "rank": rank,
                "chunk_id": chunk["chunk_id"],
                "document": chunk["document"],
                "page": chunk["page"],
                "text": chunk["text"],
                "word_count": chunk.get("word_count", 0),
                "similarity": float(score),
                "retrieval_time_ms": retrieval_time,  # per query, same for all
            })
        total_time = (time.perf_counter() - start) * 1000
        logger.debug(f"Retrieved k={k} for query '{query[:50]}...' in {total_time:.2f}ms")
        return results

    def retrieve_with_timing(self, query: str, k: int = 5) -> (List[Dict], float):
        start = time.perf_counter()
        results = self.retrieve(query, k)
        elapsed = (time.perf_counter() - start) * 1000
        return results, elapsed

# Global singleton for reuse
_retriever_instance: Optional[Retriever] = None

def get_retriever() -> Retriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance

def retrieve(query: str, k: int = 5) -> List[Dict]:
    return get_retriever().retrieve(query, k)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, default="What is eligibility for M.Tech?")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    r = get_retriever()
    results = r.retrieve(args.query, args.k)
    print(f"\nQuery: {args.query}, k={args.k}")
    for res in results:
        print(f"\nRank {res['rank']} | {res['document']} p.{res['page']} | sim={res['similarity']:.4f}")
        print(res['text'][:300] + "...")
