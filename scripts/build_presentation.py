"""
Build presentation/16_ContextLens.pptx from presentation/outline.md and the real
benchmark results in results/comparison_table.csv + results/figures/.

Usage (from the repository root):
    .venv/bin/python scripts/build_presentation.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "results" / "figures"
TABLE_PATH = ROOT / "results" / "comparison_table.csv"
OUT_PATH = ROOT / "presentation" / "16_ContextLens.pptx"

INK = RGBColor(0x1E, 0x29, 0x3B)
ACCENT = RGBColor(0x25, 0x63, 0xEB)
MUTED = RGBColor(0x5B, 0x66, 0x77)
BG = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def load_table() -> dict[str, dict]:
    rows = {}
    with open(TABLE_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["condition"]] = row
    return rows


def pct(row, key):
    v = row.get(key)
    if v in (None, ""):
        return "n/a"
    return f"{float(v) * 100:.0f}%"


def ms(row, key):
    v = row.get(key)
    if v in (None, ""):
        return "n/a"
    val = float(v)
    return f"{val/1000:.1f}s" if val >= 1000 else f"{val:.0f}ms"


def new_presentation() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def fill_bg(slide, color=BG):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def add_text(slide, left, top, width, height, text, size=18, bold=False, color=INK,
             align=PP_ALIGN.LEFT, font="Calibri"):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.alignment = align
        for run in p.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = font
    return box


def add_bullets(slide, left, top, width, height, items, size=16, color=INK, bullet_color=ACCENT):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        indent = item.startswith("  ")
        text = item.strip()
        p.text = ("    – " if indent else "•  ") + text
        p.space_after = Pt(8)
        for run in p.runs:
            run.font.size = Pt(size - 2 if indent else size)
            run.font.color.rgb = MUTED if indent else color
    return box


def add_kicker(slide, text):
    add_text(slide, Inches(0.6), Inches(0.35), Inches(8), Inches(0.4), text,
              size=14, bold=True, color=ACCENT)


def add_title(slide, text, top=Inches(0.7)):
    add_text(slide, Inches(0.6), top, Inches(12), Inches(1.0), text, size=30, bold=True, color=INK)


def footer(slide, n):
    add_text(slide, Inches(12.3), Inches(7.1), Inches(0.8), Inches(0.3), str(n),
              size=11, color=MUTED, align=PP_ALIGN.RIGHT)


def pic(slide, path, left, top, width=None, height=None):
    if width:
        slide.shapes.add_picture(str(path), left, top, width=width)
    else:
        slide.shapes.add_picture(str(path), left, top, height=height)


def build():
    t = load_table()
    prs = new_presentation()

    # Slide 1 — Title
    s = blank_slide(prs); fill_bg(s)
    add_text(s, Inches(0.8), Inches(2.3), Inches(11.7), Inches(0.5), "M.TECH AIML — MINI PROJECT · GROUP 16",
              size=16, bold=True, color=ACCENT)
    add_text(s, Inches(0.8), Inches(2.8), Inches(11.7), Inches(1.6),
              "ContextLens", size=54, bold=True, color=INK)
    add_text(s, Inches(0.8), Inches(3.9), Inches(11.7), Inches(0.9),
              "Does More Context Make RAG Smarter?", size=24, color=MUTED)
    add_bullets(s, Inches(0.8), Inches(4.9), Inches(11.5), Inches(1.6), [
        "Investigating how retrieval depth K affects answer quality in a local RAG system",
        "Documents: IIT Roorkee PG + PhD admission brochures (62 pages)",
        "Conditions compared: No-RAG, Top-1, Top-3, Top-5, Top-10, Gold-page oracle",
    ], size=16)
    footer(s, 1)

    # Slide 2 — Problem
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "REAL-WORLD PROBLEM")
    add_title(s, "RAG systems assume “more context = better”")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(7.6), Inches(4.5), [
        "A RAG pipeline retrieves the Top-K most similar chunks and feeds them to the LLM",
        "Common practice: raise K to improve coverage of the answer",
        "But a larger context window can also add:",
        "  Irrelevant or off-topic passages (noise)",
        "  Contradictory or redundant chunks",
        "  Longer prompts → higher latency and cost",
        "  More room for the LLM to misread or ignore the right passage",
        "Teams tune K by instinct, rarely by measurement",
    ], size=17)
    add_text(s, Inches(8.5), Inches(2.2), Inches(4.2), Inches(3.5),
              "PDF\n  ↓\nChunks\n  ↓\nTop-K retrieval\n  ↓\nLLM answer\n\nDoes a bigger K\nalways help?",
              size=16, color=MUTED, align=PP_ALIGN.CENTER)
    footer(s, 2)

    # Slide 3 — RQ + Hypotheses
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "RESEARCH QUESTION")
    add_title(s, "Does increasing retrieved chunks always improve answer quality?")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(12.1), Inches(2.6), [
        "H1 — Accuracy improves with K up to a point, then shows diminishing returns",
        "H2 — Context relevance and hallucination both move with K: more facts retrieved, but also more unsupported-claim risk at very low K",
        "H3 — Response time grows with K, roughly linearly through generation cost",
        "Metrics: Answer Accuracy · Context Relevance (fact recall) · Hallucination Rate · Response Time",
        "Experimental validity: K is the only variable — same documents, chunks, embeddings, prompt, model and questions across all conditions",
    ], size=17)
    footer(s, 3)

    # Slide 4 — Dataset
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "DATASET")
    add_title(s, "IIT Roorkee official admission brochures")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(6.6), Inches(4.5), [
        "Information_Brochure_2026.pdf — 25 pages, 57 PG programmes, eligibility, sponsored categories",
        "PhD_IB_A2026.pdf — 37 pages, FTRS / PTRS / Golden Girl schemes, MEQ, departments",
        "Total: 2 documents, 62 pages",
        "",
        "Benchmark: 50 questions",
        "  15 direct factual, 10 procedural, 10 eligibility,",
        "  5 conditional, 5 numerical, 5 multi-part",
        "Each question has a ground truth, required facts, source document and page",
    ], size=16)
    add_bullets(s, Inches(7.6), Inches(1.9), Inches(5.1), Inches(4.5), [
        "Gold-page validation (automatic):",
        "  25 questions — fact supported on cited page",
        "  18 questions — fact found on another page",
        "  7 questions — fact not found in document text",
        "",
        "The benchmark file states plainly that questions were generated from the PDFs, not written by domain experts — the gold-page check exists to catch bad references rather than assume the file is perfect.",
    ], size=16)
    footer(s, 4)

    # Slide 5 — Methodology / architecture
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "METHODOLOGY")
    add_title(s, "RAG pipeline, built for controlled experimentation")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(12.1), Inches(4.6), [
        "1. Preprocessing — PyMuPDF extraction, hyphenation fix, paragraph-preserving cleanup → pages.jsonl",
        "2. Chunking — 500-word chunks, 80-word overlap, paragraph-aware; the same chunk set is reused for every K so only retrieval depth changes",
        "3. Embedding + index — all-MiniLM-L6-v2 (384-d), FAISS exact inner-product index (cosine similarity)",
        "4. Retrieval — Top-K chunks per question, K ∈ {1, 3, 5, 10}, plus No-RAG and Gold-page baselines",
        "5. Generation — local MLX LLM (Qwen3-4B-Instruct), fixed prompt and generation parameters across conditions, must cite sources or abstain",
        "6. Evaluation — rule-based: fact-coverage accuracy (0–2), context fact recall, claim-level support checking (hallucination), citation validity, latency",
    ], size=16)
    footer(s, 5)

    # Slide 6 — Experimental setup
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "EXPERIMENTAL SETUP")
    add_title(s, "Paired design — K is the only variable")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(6.2), Inches(4.5), [
        "Independent variable: K ∈ {no_rag, 1, 3, 5, 10, gold}",
        "Dependent variables: accuracy, context relevance, hallucination rate, response time",
        "Held constant: documents, chunking, embedding model, FAISS index, similarity metric, question set, ground truth, LLM, prompt, generation parameters, evaluation method",
        "Design: every question answered under every condition (paired) → Wilcoxon signed-rank test per pair, Holm-corrected across comparisons",
    ], size=16)
    add_bullets(s, Inches(7.1), Inches(1.9), Inches(5.6), Inches(4.5), [
        f"Completed run: 275 question×condition answers (50 questions × 5 conditions + 25 gold-eligible)",
        "Run ID: full-50q-2026-10-12",
        "Outputs: runs.jsonl (raw), summary.json (aggregates + significance tests), results.csv, comparison_table.csv, figures/",
    ], size=16)
    footer(s, 6)

    # Slide 7 — Results
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "RESULTS")
    add_title(s, "Observed results — real run, no fabricated numbers")
    fig_w = Inches(3.05)
    figs = ["accuracy_vs_k.png", "context_relevance_vs_k.png", "hallucination_rate_vs_k.png", "response_time_vs_k.png"]
    for i, name in enumerate(figs):
        left = Inches(0.5 + i * 3.15)
        pic(s, FIG_DIR / name, left, Inches(1.8), width=fig_w)
    rows_txt = []
    for cond, label in [("k1", "Top-1"), ("k3", "Top-3"), ("k5", "Top-5"), ("k10", "Top-10")]:
        r = t[cond]
        rows_txt.append(
            f"{label}: accuracy {pct(r,'accuracy_normalised_mean')} · "
            f"context recall {pct(r,'context_fact_recall_mean')} · "
            f"hallucination {pct(r,'hallucination_rate')} · "
            f"median latency {ms(r,'total_ms_median')}"
        )
    add_bullets(s, Inches(0.6), Inches(5.6), Inches(12.1), Inches(1.7), rows_txt, size=14)
    footer(s, 7)

    # Slide 8 — Failure / interesting cases
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "INTERESTING / FAILURE CASES")
    add_title(s, "Where more context helped — and where it didn't")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(12.1), Inches(4.8), [
        f"Top-1 under-retrieves: abstention rate {pct(t['k1'],'abstention_rate')} at K=1 vs {pct(t['k10'],'abstention_rate')} at K=10 — the single best-matching chunk often doesn't contain the required fact",
        f"Accuracy rises sharply from K=1 ({pct(t['k1'],'accuracy_normalised_mean')}) to K=3 ({pct(t['k3'],'accuracy_normalised_mean')}), then flattens toward K=10 ({pct(t['k10'],'accuracy_normalised_mean')}) — diminishing returns, matching H1",
        f"Hallucination (unsupported claims) falls as K grows: {pct(t['k1'],'hallucination_rate')} at K=1 down to {pct(t['k10'],'hallucination_rate')} at K=10 — more evidence per answer, fewer unsupported statements",
        f"Latency grows roughly linearly with K: {ms(t['k1'],'total_ms_median')} at K=1 → {ms(t['k10'],'total_ms_median')} at K=10, a direct cost of longer prompts",
        f"The Gold-page oracle (ground-truth page only) reaches {pct(t['gold'],'accuracy_normalised_mean')} accuracy in {ms(t['gold'],'total_ms_median')} — faster and more accurate than Top-10, showing retrieval precision still bounds Top-K quality more than raw K does",
        "Full per-question detail: results/results.csv; aggregate significance tests: results/benchmark/full-50q-2026-10-12/summary.json (paired_tests)",
    ], size=16)
    footer(s, 8)

    # Slide 9 — Findings + limitations
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "FINDINGS & LIMITATIONS")
    add_title(s, "More context helps — up to a point, and at a cost")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(6.2), Inches(4.6), [
        "Findings",
        "  Accuracy: rises sharply K=1→3, then plateaus (H1 supported)",
        "  Context relevance: increases monotonically with K",
        "  Hallucination: decreases monotonically with K — opposite of the naive “more noise” intuition for this dataset",
        "  Latency: increases ~linearly with K (H3 supported)",
        "  Statistically significant gains for accuracy and latency between most K pairs after Holm correction (see summary.json)",
    ], size=16)
    add_bullets(s, Inches(7.1), Inches(1.9), Inches(5.6), Inches(4.6), [
        "Limitations",
        "  2 documents, 62 pages — single narrow domain",
        "  MiniLM is a lightweight embedding model",
        "  Evaluation is rule-based (lexical heuristics), not human-judged",
        "  Benchmark questions were generated from the PDFs, not written by domain experts",
        "  Fixed chunking (500/80 words) not swept",
        "  50 questions — moderate statistical power",
    ], size=16)
    footer(s, 9)

    # Slide 10 — Conclusion
    s = blank_slide(prs); fill_bg(s)
    add_kicker(s, "CONCLUSION")
    add_title(s, "K is a tuned hyperparameter, not “as much as fits”")
    add_bullets(s, Inches(0.6), Inches(1.9), Inches(6.2), Inches(4.6), [
        "Conclusion",
        "  More retrieved context did improve this system, but with diminishing accuracy gains after K=3 and a near-linear latency cost",
        "  Retrieval precision (the Gold-page condition) matters more than raw K",
        "  Experimental validity came from holding everything but K constant",
    ], size=16)
    add_bullets(s, Inches(7.1), Inches(1.9), Inches(5.6), Inches(4.6), [
        "Future work",
        "  Adaptive K based on query complexity or retrieval confidence",
        "  Stronger embeddings (E5, BGE) and re-ranking",
        "  Context compression / summarisation at high K",
        "  Human evaluation alongside the lexical heuristics",
        "  Multi-hop questions, larger K, more domains",
    ], size=16)
    footer(s, 10)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT_PATH)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
