from backend.app.research.benchmark import _holm, aggregate, compute_metrics, paired_tests


def record(qid, condition, score, total_ms=100.0):
    return {
        "question_id": qid,
        "condition": condition,
        "metrics": {"accuracy": {"score": score}},
        "latency": {"total_ms": total_ms},
    }


def test_holm_correction_is_monotone_and_capped():
    adjusted = _holm([0.01, 0.04, 0.03, None])
    assert adjusted[3] is None
    assert adjusted[0] == 0.03  # 3 * 0.01
    assert adjusted[2] == 0.06  # max(0.03, 2 * 0.03)
    assert adjusted[1] == 0.06  # max(0.06, 1 * 0.04)
    assert all(p <= 1 for p in adjusted if p is not None)


def test_paired_tests_skip_small_or_identical_samples():
    recs = [record(f"Q{i}", "k1", 1) for i in range(3)] + [record(f"Q{i}", "k3", 1) for i in range(3)]
    acc = [r for r in paired_tests(recs, ["k1", "k3"]) if r["metric"] == "accuracy_score"][0]
    assert acc["p_value"] is None and "too few" in acc["note"]
    recs = [record(f"Q{i}", "k1", 0) for i in range(8)] + [record(f"Q{i}", "k3", 2 if i % 4 else 1) for i in range(8)]
    acc = [r for r in paired_tests(recs, ["k1", "k3"]) if r["metric"] == "accuracy_score"][0]
    assert acc["n"] == 8 and acc["p_value"] is not None and acc["mean_diff_b_minus_a"] > 0


def test_aggregate_excludes_errors_and_reports_counts():
    recs = [record("Q1", "k1", 2), record("Q2", "k1", 0), {"question_id": "Q3", "condition": "k1", "error": "boom"}]
    agg = aggregate(recs)
    assert agg["n"] == 3 and agg["errors"] == 1
    assert agg["accuracy_normalised_mean"] == 0.5
    assert agg["accuracy_score_counts"] == {"0": 1, "1": 0, "2": 1}


def test_compute_metrics_uses_only_sources_in_prompt():
    rec = {
        "condition": "k3",
        "answer": "The application fee is Rs 5000 [S1].",
        "required_facts": ["Rs 5000"],
        "gold": {"document": "a.pdf", "page": 2, "validation": "supported_on_cited_page"},
        "retrieved": [
            {"text": "The application fee is Rs 5000.", "document_name": "a.pdf", "pages": [2]},
            {"text": "Unrelated hostel text.", "document_name": "a.pdf", "pages": [5]},
        ],
        "generation": {"sources_in_prompt": 1},
        "citations": [{"source_label": "S1", "document_name": "a.pdf", "pages": [2]}],
        "invalid_citations": [],
    }
    m = compute_metrics(rec)
    assert m["accuracy"]["score"] == 2
    assert m["context"] == {"fact_recall": 1.0, "fact_bearing_chunk_precision": 1.0, "gold_page_retrieved": True}
    assert m["citations"]["cites_gold_page"] is True and m["citations"]["validity"] == 1.0
    assert m["claims"]["supported"] == 1 and m["claims"]["contradicted"] is None
