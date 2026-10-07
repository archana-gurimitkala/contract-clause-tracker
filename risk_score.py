from extractor import CLAUSE_TYPES

FLAG_PENALTY = 15
MISSING_PENALTY = 4

BANDS = [
    (85, "Low Risk", "good"),
    (60, "Moderate Risk", "warning"),
    (35, "Elevated Risk", "serious"),
    (0, "High Risk", "critical"),
]


def compute_risk_score(result):
    """Heuristic 0-100 score from flagged/missing clause counts.
    Not a legal risk rating — a quick triage signal, not a substitute for attorney review."""
    score = 100
    for ct in CLAUSE_TYPES:
        clause = result["clauses"][ct]
        if clause["flagged"]:
            score -= FLAG_PENALTY
        elif not clause["found"]:
            score -= MISSING_PENALTY
    score = max(0, min(100, score))

    for threshold, label, status in BANDS:
        if score >= threshold:
            return {"score": score, "label": label, "status": status}
    return {"score": score, "label": "High Risk", "status": "critical"}
