"""
Embeddings generation.
Default: sentence-transformers/all-MiniLM-L6-v2
Fallback: TF-IDF (if torch not available) for offline testing.
Stores: embeddings.npy + faiss.index + metadata preserved via chunks.jsonl
CLI: python -m src.embeddings
"""
import os
import json
import pickle
from pathlib import Path
import numpy as np
from typing import List, Dict
import time

from .config import CHUNKS_JSONL, EMBEDDINGS_NPY_PATH, FAISS_INDEX_PATH, EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE, DATA_PROCESSED_DIR
from .utils import load_jsonl, logger

def load_chunks() -> List[Dict]:
    if not CHUNKS_JSONL.exists():
        raise FileNotFoundError(f"Chunks file not found: {CHUNKS_JSONL}. Run chunking first.")
    chunks = load_jsonl(CHUNKS_JSONL)
    logger.info(f"Loaded {len(chunks)} chunks")
    return chunks

def get_embedding_model(model_name: str):
    """Try to load sentence-transformers, fallback to TF-IDF"""
    try:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {model_name}")
        model = SentenceTransformer(model_name)
        # test
        _ = model.encode(["test"], show_progress_bar=False)
        logger.info("SentenceTransformer model loaded successfully")
        return model, "sentence_transformer"
    except Exception as e:
        logger.warning(f"Failed to load SentenceTransformer {model_name}: {e}")
        logger.warning("Falling back to TF-IDF embeddings for offline testing")
        return None, "tfidf"

def generate_embeddings_sentence_transformer(model, texts: List[str], batch_size: int = 32) -> np.ndarray:
    from tqdm import tqdm
    all_embs = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
        batch = texts[i:i+batch_size]
        emb = model.encode(batch, show_progress_bar=False, normalize_embeddings=True)
        all_embs.append(emb)
    return np.vstack(all_embs)

def generate_embeddings_tfidf(texts: List[str]) -> (np.ndarray, object):
    from sklearn.feature_extraction.text import TfidfVectorizer
    logger.info("Generating TF-IDF embeddings (fallback)")
    vectorizer = TfidfVectorizer(max_features=384, stop_words='english', ngram_range=(1,2))
    tfidf_matrix = vectorizer.fit_transform(texts)
    embeddings = tfidf_matrix.toarray().astype(np.float32)
    # L2 normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms==0, 1, norms)
    embeddings = embeddings / norms
    return embeddings, vectorizer

def build_faiss_index(embeddings: np.ndarray, metric: str = "cosine"):
    import faiss
    dim = embeddings.shape[1]
    logger.info(f"Building FAISS index: dim={dim}, metric={metric}, n={embeddings.shape[0]}")
    if metric == "cosine":
        # For cosine, we use Inner Product on normalized vectors
        index = faiss.IndexFlatIP(dim)
    else:
        index = faiss.IndexFlatL2(dim)
    # embeddings should be float32
    embeddings = embeddings.astype(np.float32)
    index.add(embeddings)
    logger.info(f"FAISS index built with {index.ntotal} vectors")
    return index

def main(force_recompute: bool = False):
    chunks = load_chunks()
    texts = [c["text"] for c in chunks]

    # Check if embeddings already exist and not forced
    if EMBEDDINGS_NPY_PATH.exists() and FAISS_INDEX_PATH.exists() and not force_recompute:
        logger.info("Embeddings and index already exist. Skipping recomputation. Use force_recompute=True to rebuild.")
        print(f"Embeddings exist: {EMBEDDINGS_NPY_PATH}")
        print(f"Index exists: {FAISS_INDEX_PATH}")
        return

    model, model_type = get_embedding_model(EMBEDDING_MODEL)

    start = time.time()
    if model_type == "sentence_transformer":
        embeddings = generate_embeddings_sentence_transformer(model, texts, EMBEDDING_BATCH_SIZE)
        # Save model info
        meta = {
            "model": EMBEDDING_MODEL,
            "type": "sentence_transformer",
            "dim": embeddings.shape[1],
            "num_chunks": len(chunks),
        }
    else:
        embeddings, vectorizer = generate_embeddings_tfidf(texts)
        meta = {
            "model": "tfidf_fallback",
            "type": "tfidf",
            "dim": embeddings.shape[1],
            "num_chunks": len(chunks),
        }
        # Save vectorizer for query embedding
        vectorizer_path = DATA_PROCESSED_DIR / "tfidf_vectorizer.pkl"
        with open(vectorizer_path, 'wb') as f:
            pickle.dump(vectorizer, f)
        logger.info(f"Saved TF-IDF vectorizer to {vectorizer_path}")

    elapsed = time.time() - start
    logger.info(f"Generated {embeddings.shape[0]} embeddings in {elapsed:.2f}s, shape {embeddings.shape}")

    # Save embeddings
    np.save(str(EMBEDDINGS_NPY_PATH), embeddings)
    logger.info(f"Saved embeddings to {EMBEDDINGS_NPY_PATH}")

    # Build FAISS
    index = build_faiss_index(embeddings, metric="cosine")
    import faiss
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    logger.info(f"Saved FAISS index to {FAISS_INDEX_PATH}")

    # Save meta
    meta_path = DATA_PROCESSED_DIR / "embedding_meta.json"
    meta["generation_time_sec"] = elapsed
    meta["embedding_path"] = str(EMBEDDINGS_NPY_PATH)
    meta["index_path"] = str(FAISS_INDEX_PATH)
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    
    print("\n=== Embeddings Summary ===")
    for k,v in meta.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force recompute")
    args = parser.parse_args()
    main(force_recompute=args.force)
