"""
Evaluation metrics for ContextLens:
- Answer Accuracy (0-2 scale, normalized)
- Context Relevance (0-3 per chunk, aggregated)
- Hallucination Rate (claim-level SUPPORTED/UNSUPPORTED/CONTRADICTED)
- Response Time (retrieval, generation, total)

Supports both rule-based and optional LLM-judge evaluation.
"""
import re
import json
from typing import List, Dict, Tuple, Any
import time
from .config import get_llm_config, EVAL_USE_LLM_JUDGE
from .utils import logger
from .generator import get_llm_provider

# ---------------- Answer Accuracy ----------------
def evaluate_accuracy_rule_based(question: str, ground_truth: str, required_facts: List[str], generated_answer: str) -> Dict:
    """
    Rule-based accuracy 0-2:
    0 = incorrect / missing essential answer
    1 = partially correct
    2 = correct and sufficiently complete
    Uses keyword / required facts coverage.
    """
    if not generated_answer or "insufficient information" in generated_answer.lower():
        # Check if ground truth actually says insufficient? Usually not, so 0
        return {"score": 0, "reason": "Answer says insufficient information", "method": "rule_based"}

    gt_lower = ground_truth.lower()
    ans_lower = generated_answer.lower()

    # Count required facts present
    if not required_facts:
        # Fallback: check if ground truth keywords overlap >50%
        gt_words = set(re.findall(r'\w+', gt_lower))
        ans_words = set(re.findall(r'\w+', ans_lower))
        overlap = len(gt_words & ans_words) / max(1, len(gt_words))
        if overlap >= 0.6:
            score = 2
        elif overlap >= 0.3:
            score = 1
        else:
            score = 0
        return {"score": score, "overlap": overlap, "method": "rule_based_keyword_overlap"}

    facts_covered = 0
    covered_facts = []
    missing_facts = []
    for fact in required_facts:
        fact_lower = fact.lower()
        # check if fact keywords present (at least 60% of fact words in answer)
        fact_words = set(re.findall(r'\w+', fact_lower))
        if not fact_words:
            continue
        present = sum(1 for w in fact_words if w in ans_lower)
        coverage = present / len(fact_words)
        if coverage >= 0.6:
            facts_covered += 1
            covered_facts.append(fact)
        else:
            missing_facts.append(fact)

    total_facts = len(required_facts)
    coverage_ratio = facts_covered / total_facts if total_facts else 0

    if coverage_ratio >= 0.8:
        score = 2
    elif coverage_ratio >= 0.4:
        score = 1
    else:
        score = 0

    return {
        "score": score,
        "coverage_ratio": coverage_ratio,
        "facts_covered": facts_covered,
        "total_facts": total_facts,
        "covered_facts": covered_facts,
        "missing_facts": missing_facts,
        "method": "rule_based_required_facts"
    }

def evaluate_accuracy_llm_judge(question: str, ground_truth: str, generated_answer: str, required_facts: List[str]) -> Dict:
    """Use LLM as judge with strict JSON schema"""
    provider = get_llm_provider()
    if provider.provider == "mock":
        # Fallback to rule based
        return evaluate_accuracy_rule_based(question, ground_truth, required_facts, generated_answer)

    system = """You are an evaluator for RAG answers. 
Given question, ground truth, required facts, and generated answer, score accuracy 0-2:
0 = incorrect / missing essential answer
1 = partially correct (some facts missing or partially correct)
2 = correct and sufficiently complete (covers all required facts)

Return ONLY valid JSON with fields: score (0,1,2), reason (string), covered_facts (list), missing_facts (list).
"""
    user = f"""Question: {question}
Ground Truth: {ground_truth}
Required Facts: {json.dumps(required_facts)}
Generated Answer: {generated_answer}

Evaluate:"""

    try:
        from openai import OpenAI
        # Reuse provider client if available
        if provider.client:
            resp = provider.client.chat.completions.create(
                model=provider.model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=0.0,
                max_tokens=500,
                response_format={"type":"json_object"} if provider.provider=="openai" else None
            )
            content = resp.choices[0].message.content
            # Try parse json
            try:
                parsed = json.loads(content)
                # validate
                score = int(parsed.get("score",0))
                score = max(0, min(2, score))
                return {"score": score, "reason": parsed.get("reason",""), "covered_facts": parsed.get("covered_facts",[]), "missing_facts": parsed.get("missing_facts",[]), "method":"llm_judge", "raw": content}
            except Exception as e:
                logger.warning(f"Failed to parse LLM judge JSON: {e}, content: {content[:500]}")
                # fallback
                return evaluate_accuracy_rule_based(question, ground_truth, required_facts, generated_answer)
    except Exception as e:
        logger.warning(f"LLM judge failed: {e}, fallback to rule")
        return evaluate_accuracy_rule_based(question, ground_truth, required_facts, generated_answer)

def evaluate_accuracy(question: str, ground_truth: str, required_facts: List[str], generated_answer: str) -> Dict:
    if EVAL_USE_LLM_JUDGE:
        return evaluate_accuracy_llm_judge(question, ground_truth, generated_answer, required_facts)
    else:
        return evaluate_accuracy_rule_based(question, ground_truth, required_facts, generated_answer)

# ---------------- Context Relevance ----------------
def evaluate_relevance_rule_based(question: str, retrieved_chunks: List[Dict]) -> Dict:
    """
    0-3 per chunk:
    0 irrelevant
    1 weakly related
    2 useful
    3 directly useful for answering
    Aggregate: sum(scores)/(3*K)
    Rule based uses keyword overlap between question and chunk + ground truth heuristics
    """
    q_words = set(re.findall(r'\w+', question.lower()))
    # Remove stopwords simple
    stopwords = {"what","is","the","for","of","and","in","to","a","an","how","when","where","does","do","are","be","required"}
    q_keywords = q_words - stopwords

    chunk_scores = []
    for chunk in retrieved_chunks:
        text = chunk.get("text","").lower()
        text_words = set(re.findall(r'\w+', text))
        overlap = len(q_keywords & text_words) / max(1, len(q_keywords)) if q_keywords else 0

        # Additional heuristics: if chunk contains numbers when question asks numerical, boost
        # Simple scoring
        if overlap >= 0.5:
            score = 3
        elif overlap >= 0.3:
            score = 2
        elif overlap >= 0.1:
            score = 1
        else:
            score = 0
        
        # If question mentions eligibility and chunk mentions eligibility, boost
        if "eligib" in question.lower() and "eligib" in text:
            score = max(score, 2)
        if "fee" in question.lower() and ("fee" in text or "rs" in text or "rupee" in text):
            score = max(score, 2)

        chunk_scores.append({
            "chunk_id": chunk.get("chunk_id"),
            "relevance_score": score,
            "overlap": overlap,
            "method": "rule_based"
        })

    total_score = sum(c["relevance_score"] for c in chunk_scores)
    k = len(retrieved_chunks)
    relevance = total_score / (3*k) if k>0 else 0

    return {
        "context_relevance": relevance,
        "total_score": total_score,
        "max_possible": 3*k,
        "chunk_scores": chunk_scores,
        "method": "rule_based"
    }

def evaluate_relevance_llm_judge(question: str, retrieved_chunks: List[Dict]) -> Dict:
    provider = get_llm_provider()
    if provider.provider == "mock":
        return evaluate_relevance_rule_based(question, retrieved_chunks)

    # For each chunk, ask LLM to score 0-3
    # To save tokens, batch? We'll do one call with all chunks
    system = """You are a relevance evaluator. For each retrieved chunk, score 0-3:
0 = irrelevant
1 = weakly related
2 = useful
3 = directly useful for answering the question

Return JSON: {"scores": [{"chunk_id": "...", "score": 0-3, "reason": "..."}]}
"""
    chunks_text = "\n".join([f"Chunk {i+1} ID {c.get('chunk_id')} : {c.get('text')[:500]}..." for i,c in enumerate(retrieved_chunks)])
    user = f"Question: {question}\n\nRetrieved Chunks:\n{chunks_text}\n\nEvaluate relevance:"

    try:
        if provider.client:
            resp = provider.client.chat.completions.create(
                model=provider.model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=0.0,
                max_tokens=1000,
            )
            content = resp.choices[0].message.content
            parsed = json.loads(content)
            scores = parsed.get("scores",[])
            # map
            total = sum(s.get("score",0) for s in scores)
            k = len(retrieved_chunks)
            relevance = total / (3*k) if k else 0
            return {
                "context_relevance": relevance,
                "total_score": total,
                "max_possible": 3*k,
                "chunk_scores": scores,
                "method": "llm_judge",
                "raw": content
            }
    except Exception as e:
        logger.warning(f"LLM relevance judge failed: {e}, fallback to rule")
    return evaluate_relevance_rule_based(question, retrieved_chunks)

def evaluate_relevance(question: str, retrieved_chunks: List[Dict]) -> Dict:
    if EVAL_USE_LLM_JUDGE:
        return evaluate_relevance_llm_judge(question, retrieved_chunks)
    else:
        return evaluate_relevance_rule_based(question, retrieved_chunks)

# ---------------- Hallucination ----------------
def extract_claims(answer: str) -> List[str]:
    """Naive claim extraction: split by sentences"""
    if not answer:
        return []
    # Remove citations like [doc, p. X]
    cleaned = re.sub(r'\[.*?\]', '', answer)
    sentences = re.split(r'(?<=[.!?])\s+', cleaned)
    claims = [s.strip() for s in sentences if len(s.strip().split()) >= 4]  # at least 4 words
    return claims

def evaluate_hallucination_rule_based(answer: str, retrieved_chunks: List[Dict]) -> Dict:
    """
    Claim-level: SUPPORTED, UNSUPPORTED, CONTRADICTED
    Hallucination Rate = (UNSUPPORTED+CONTRADICTED)/TOTAL
    Rule based: check if claim keywords appear in retrieved context
    """
    claims = extract_claims(answer)
    if not claims:
        return {"hallucination_rate": 0.0, "total_claims": 0, "supported":0, "unsupported":0, "contradicted":0, "claims": [], "method":"rule_based"}

    # Build combined context text lower
    context_text = " ".join([c.get("text","") for c in retrieved_chunks]).lower()
    context_words = set(re.findall(r'\w+', context_text))

    results = []
    supported = 0
    unsupported = 0
    contradicted = 0  # rule based cannot detect contradiction easily, treat as unsupported unless explicit negation mismatch

    for claim in claims:
        claim_lower = claim.lower()
        claim_words = set(re.findall(r'\w+', claim_lower))
        # Remove stopwords
        stopwords = {"the","is","are","was","were","be","been","a","an","of","and","in","to","for","with","on","at","by","it","this","that"}
        claim_keywords = claim_words - stopwords
        if not claim_keywords:
            # trivial claim, consider supported
            label = "SUPPORTED"
            supported+=1
        else:
            overlap = len(claim_keywords & context_words) / max(1, len(claim_keywords))
            if overlap >= 0.6:
                label = "SUPPORTED"
                supported+=1
            elif overlap >= 0.3:
                # weakly supported -> treat as SUPPORTED for lenient but log
                label = "SUPPORTED"
                supported+=1
            else:
                # Check for contradiction heuristic: if claim contains "not" and context contains positive without negation? Complex, mark unsupported
                label = "UNSUPPORTED"
                unsupported+=1

        results.append({
            "claim": claim,
            "label": label,
            "overlap": overlap if 'overlap' in locals() else 0,
        })

    total = len(claims)
    hallucination_rate = (unsupported + contradicted) / total if total else 0

    return {
        "hallucination_rate": hallucination_rate,
        "total_claims": total,
        "supported": supported,
        "unsupported": unsupported,
        "contradicted": contradicted,
        "claims": results,
        "method": "rule_based"
    }

def evaluate_hallucination_llm_judge(answer: str, retrieved_chunks: List[Dict]) -> Dict:
    provider = get_llm_provider()
    if provider.provider == "mock":
        return evaluate_hallucination_rule_based(answer, retrieved_chunks)

    system = """You are a faithfulness evaluator. Given retrieved context and generated answer, extract factual claims and label each:
SUPPORTED = context directly supports claim
UNSUPPORTED = context does not establish claim
CONTRADICTED = context contradicts claim

Return JSON: {"claims": [{"claim": "...", "label": "SUPPORTED|UNSUPPORTED|CONTRADICTED", "reason": "..."}]}
"""
    context_str = "\n".join([f"[{c.get('document')}, p.{c.get('page')}] {c.get('text')[:600]}" for c in retrieved_chunks])
    user = f"Context:\n{context_str}\n\nAnswer:\n{answer}\n\nEvaluate:"

    try:
        if provider.client:
            resp = provider.client.chat.completions.create(
                model=provider.model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=0.0,
                max_tokens=1500,
            )
            content = resp.choices[0].message.content
            parsed = json.loads(content)
            claims = parsed.get("claims",[])
            supported = sum(1 for c in claims if c.get("label")=="SUPPORTED")
            unsupported = sum(1 for c in claims if c.get("label")=="UNSUPPORTED")
            contradicted = sum(1 for c in claims if c.get("label")=="CONTRADICTED")
            total = len(claims)
            rate = (unsupported+contradicted)/total if total else 0
            return {
                "hallucination_rate": rate,
                "total_claims": total,
                "supported": supported,
                "unsupported": unsupported,
                "contradicted": contradicted,
                "claims": claims,
                "method": "llm_judge",
                "raw": content
            }
    except Exception as e:
        logger.warning(f"LLM hallucination judge failed: {e}, fallback")
    return evaluate_hallucination_rule_based(answer, retrieved_chunks)

def evaluate_hallucination(answer: str, retrieved_chunks: List[Dict]) -> Dict:
    if EVAL_USE_LLM_JUDGE:
        return evaluate_hallucination_llm_judge(answer, retrieved_chunks)
    else:
        return evaluate_hallucination_rule_based(answer, retrieved_chunks)

# Unified evaluation
def evaluate_run(question: str, ground_truth: str, required_facts: List[str], generated_answer: str, retrieved_chunks: List[Dict]) -> Dict:
    acc = evaluate_accuracy(question, ground_truth, required_facts, generated_answer)
    rel = evaluate_relevance(question, retrieved_chunks)
    hall = evaluate_hallucination(generated_answer, retrieved_chunks)

    return {
        "answer_accuracy": acc.get("score",0)/2.0 if "score" in acc else 0,  # normalized 0-1
        "answer_accuracy_raw": acc,
        "context_relevance": rel.get("context_relevance",0),
        "context_relevance_raw": rel,
        "hallucination_rate": hall.get("hallucination_rate",0),
        "hallucination_raw": hall,
    }
