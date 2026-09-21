import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import RESULTS_DIR
from src.utils import load_json
import json
import pandas as pd

class ExperimentService:
    def get_summary(self):
        # Load comparison_table.csv if exists
        comp_path = RESULTS_DIR / "comparison_table.csv"
        summary_path = RESULTS_DIR / "results.csv"
        stats = {
            "total_runs": 0,
            "k_values": [1,3,5,10],
            "aggregated": [],
            "figures": [],
            "has_results": False,
        }
        if comp_path.exists():
            try:
                df = pd.read_csv(comp_path)
                stats["aggregated"] = df.to_dict(orient="records")
                stats["has_results"] = True
            except Exception as e:
                print(f"Failed to load comparison table: {e}")
        if summary_path.exists():
            try:
                df = pd.read_csv(summary_path)
                stats["total_runs"] = len(df)
            except:
                pass
        # figures
        figures_dir = RESULTS_DIR / "figures"
        if figures_dir.exists():
            stats["figures"] = [f.name for f in figures_dir.glob("*.png")]
        return stats

    def get_question_result(self, question_id: str):
        raw_path = RESULTS_DIR / "raw_runs.jsonl"
        if not raw_path.exists():
            return None
        results = []
        with open(raw_path, 'r') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("question_id") == question_id:
                        results.append(rec)
                except:
                    continue
        if not results:
            return None
        return {
            "question_id": question_id,
            "question": results[0].get("question"),
            "results": results
        }

    def get_all_results(self):
        csv_path = RESULTS_DIR / "results.csv"
        if not csv_path.exists():
            return []
        try:
            df = pd.read_csv(csv_path)
            return df.to_dict(orient="records")
        except Exception as e:
            print(f"Failed to load results: {e}")
            return []

def get_experiment_service():
    return ExperimentService()
