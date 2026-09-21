from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_PROCESSED_DIR = Path(os.getenv("DATA_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed"))
BENCHMARK_PATH = Path(os.getenv("BENCHMARK_PATH", PROJECT_ROOT / "data" / "benchmark" / "ContextLens_Benchmark_50_Questions.json"))
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", PROJECT_ROOT / "results"))

# For API
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

# CORS
FRONTEND_URL = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:3000")
