"""
Central configuration for ContextLens.
All paths and hyperparams in one place, env-overridable.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent

# Data paths
DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", PROJECT_ROOT / "data" / "raw"))
DATA_PROCESSED_DIR = Path(os.getenv("DATA_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed"))
BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark"
BENCHMARK_PATH = Path(os.getenv("BENCHMARK_PATH", BENCHMARK_DIR / "ContextLens_Benchmark_50_Questions.json"))
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", PROJECT_ROOT / "results"))
FIGURES_DIR = RESULTS_DIR / "figures"

# Documents
PDF_FILES = [
    DATA_RAW_DIR / "Information_Brochure_2026.pdf",
    DATA_RAW_DIR / "PhD_IB_A2026.pdf",
]

# Chunking
CHUNK_SIZE_WORDS = int(os.getenv("CHUNK_SIZE_WORDS", "500"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "80"))

# Embeddings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
EMBEDDING_BATCH_SIZE = 32
FAISS_INDEX_PATH = DATA_PROCESSED_DIR / "faiss.index"
EMBEDDINGS_NPY_PATH = DATA_PROCESSED_DIR / "embeddings.npy"
CHUNKS_JSONL = DATA_PROCESSED_DIR / "chunks.jsonl"
PAGES_JSONL = DATA_PROCESSED_DIR / "pages.jsonl"

# Retrieval
TOP_K_VALUES = [int(x.strip()) for x in os.getenv("TOP_K_VALUES", "1,3,5,10").split(",")]
RETRIEVAL_METRIC = os.getenv("RETRIEVAL_METRIC", "cosine")

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()  # gemini, openai, groq, openrouter, ollama, mock
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Evaluation
EVAL_USE_LLM_JUDGE = os.getenv("EVAL_USE_LLM_JUDGE", "false").lower() == "true"

# Generation params (kept constant across K)
GENERATION_TEMPERATURE = 0.1
GENERATION_MAX_TOKENS = 512
GENERATION_SYSTEM_PROMPT = """You are a helpful assistant for IIT Roorkee admission queries. 
Answer ONLY using the provided retrieved context. Do not use external knowledge.
If the context does not contain enough information, say: "Insufficient information in the provided documents."
Always cite sources as [DocumentName.pdf, p. X] where X is page number from metadata.
Be concise, factual, and faithful to the context.
If multiple chunks contain relevant info, synthesize them but keep citations.
"""

# Ensure dirs exist
for d in [DATA_PROCESSED_DIR, BENCHMARK_DIR, RESULTS_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def get_llm_config():
    return {
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "api_key": {"gemini": GEMINI_API_KEY, "groq": GROQ_API_KEY}.get(LLM_PROVIDER, OPENAI_API_KEY),
        "base_url": GEMINI_BASE_URL if LLM_PROVIDER == "gemini" else OPENAI_BASE_URL,
        "ollama_url": OLLAMA_BASE_URL,
        "temperature": GENERATION_TEMPERATURE,
        "max_tokens": GENERATION_MAX_TOKENS,
    }
