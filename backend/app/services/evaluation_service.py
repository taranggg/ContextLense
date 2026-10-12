"""
Automatic, rule-based evaluation signals.

These are lexical heuristics, not semantic judgements:
- "lexically supported" means most of a claim's content words and all of its
  numbers appear in the supplied evidence. It does not prove entailment.
- "unsupported" means not established by the supplied evidence; it does not
  mean the claim is false.
- Contradictions cannot be detected lexically, so they are not reported.

Answer accuracy keeps the original ContextLens rubric (0 = incorrect/missing,
1 = partial, 2 = correct and complete) computed from required-fact coverage
(>= 80% of facts -> 2, >= 40% -> 1), with each fact counted as present when
>= 60% of its content terms appear in the answer.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schemas import ClaimCheck, ConditionMetrics
from .prompts import is_abstention
from .rag_service import content_terms, parse_citation_labels

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CITATION_STRIP_RE = re.compile(r"\[[^\]]*\]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")

FACT_TERM_THRESHOLD = 0.6
ACCURACY_FULL = 0.8
ACCURACY_PARTIAL = 0.4
CLAIM_SUPPORT_THRESHOLD = 0.6


def numbers_in(text: str) -> set[str]:
    out = set()
    for raw in _NUMBER_RE.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if n.endswith(".0"):
            n = n[:-2]
        if n:
            out.add(n)
    return out


def fact_present(fact: str, text_terms: set[str], text_numbers: set[str]) -> bool:
    terms = content_terms(fact)
    if not terms:
        return False
    nums = numbers_in(fact)
    if nums and not nums <= text_numbers:
        return False
    return len(terms & text_terms) / len(terms) >= FACT_TERM_THRESHOLD


def fact_coverage(required_facts: list[str], text: str) -> tuple[list[str], list[str]]:
    terms, nums = content_terms(text), numbers_in(text)
    covered = [f for f in required_facts if fact_present(f, terms, nums)]
    missing = [f for f in required_facts if f not in covered]
    return covered, missing


def score_accuracy(required_facts: list[str], answer: str) -> dict:
    """0/1/2 score from required-fact coverage. Abstentions score 0."""
    if not answer.strip() or is_abstention(answer):
        return {"score": 0, "coverage": 0.0, "covered_facts": [], "missing_facts": list(required_facts), "abstained": True}
    covered, missing = fact_coverage(required_facts, _CITATION_STRIP_RE.sub(" ", answer))
    coverage = len(covered) / len(required_facts) if required_facts else 0.0
    score = 2 if coverage >= ACCURACY_FULL else 1 if coverage >= ACCURACY_PARTIAL else 0
    return {"score": score, "coverage": round(coverage, 4), "covered_facts": covered, "missing_facts": missing, "abstained": False}


def extract_claims(answer: str) -> list[str]:
    cleaned = _CITATION_STRIP_RE.sub("", answer)
    claims = []
    for sentence in _SENTENCE_RE.split(cleaned):
        s = sentence.strip(" -*•\t")
        if len(s.split()) >= 4 and not is_abstention(s):
            claims.append(s)
    return claims


def check_claims(answer: str, evidence: str) -> list[ClaimCheck]:
    ev_terms, ev_nums = content_terms(evidence), numbers_in(evidence)
    checks = []
    for claim in extract_claims(answer):
        terms = content_terms(claim)
        ratio = len(terms & ev_terms) / len(terms) if terms else 1.0
        missing_nums = sorted(numbers_in(claim) - ev_nums)
        supported = ratio >= CLAIM_SUPPORT_THRESHOLD and not missing_nums
        checks.append(
            ClaimCheck(
                claim=claim,
                label="supported" if supported else "unsupported",
                support_ratio=round(ratio, 3),
                missing_numbers=missing_nums,
            )
        )
    return checks


def condition_metrics(answer: str, evidence: str, valid_labels: Optional[set[str]]) -> ConditionMetrics:
    """`valid_labels` is None for the no-RAG baseline, where citations are not applicable."""
    labels = parse_citation_labels(answer)
    invalid = [l for l in labels if valid_labels is not None and l not in valid_labels]
    checks = check_claims(answer, evidence) if evidence else []
    return ConditionMetrics(
        abstained=is_abstention(answer),
        citation_count=len(labels),
        invalid_citation_count=len(invalid),
        citation_validity=(round((len(labels) - len(invalid)) / len(labels), 4) if labels and valid_labels is not None else None),
        claims_total=len(checks),
        claims_lexically_supported=sum(1 for c in checks if c.label == "supported"),
        claims_lexically_unsupported=sum(1 for c in checks if c.label == "unsupported"),
        claim_checks=checks,
    )
