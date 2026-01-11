from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import re

app = FastAPI(title="Subject Line Scorer", version="1.0.0")

# -------------------------
# Scoring rules
# -------------------------
SPAM_TERMS = [
    "free", "guarantee", "guaranteed", "urgent",
    "act now", "limited time", "winner", "cash", "100%"
]
ALL_CAPS_PATTERN = re.compile(r"\b[A-Z]{4,}\b")

# -------------------------
# Models (Opal typically wraps inputs inside "parameters")
# -------------------------
class ScoreParams(BaseModel):
    subject_lines: List[str] = Field(..., description="List of email subject lines")

class ToolRequest(BaseModel):
    parameters: ScoreParams
    # Opal may send extra metadata; keep optional so it never breaks validation
    auth: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, Any]] = None
    chat_metadata: Optional[Dict[str, Any]] = None

@app.get("/health")
def health():
    return {"status": "ok"}

# -------------------------
# Opal Discovery (IMPORTANT: parameters is a LIST + endpoint/http_method)
# -------------------------
@app.get("/discovery")
def discovery():
    return {
        "functions": [
            {
                "name": "subject_line_scorer",
                "description": "Scores email subject lines for length/spam risk and returns the best subject.",
                "parameters": [
                    {
                        "name": "subject_lines",
                        "type": "array",
                        "description": "A list of email subject lines to evaluate",
                        "required": True
                    }
                ],
                "endpoint": "/tools/subject-line-scorer",
                "http_method": "POST"
            }
        ]
    }

# -------------------------
# Tool endpoint Opal will call
# -------------------------
@app.post("/tools/subject-line-scorer")
def subject_line_scorer(req: ToolRequest):
    subject_lines = req.parameters.subject_lines
    results = []

    for subject in subject_lines:
        subject = (subject or "").strip()
        length = len(subject)
        score = 100
        warnings = []

        if length == 0:
            results.append({
                "subject": subject,
                "score": 0,
                "length": 0,
                "spam_risk": "High",
                "warnings": ["Empty subject line"]
            })
            continue

        if length > 60:
            score -= 25
            warnings.append("Too long (60+ characters)")
        elif length > 45:
            score -= 15
            warnings.append("Long (45+ characters)")

        lower = subject.lower()
        for term in SPAM_TERMS:
            if term in lower:
                score -= 20
                warnings.append(f"Spam term detected: '{term}'")

        if subject.count("!") >= 2:
            score -= 10
            warnings.append("Too many exclamation marks")

        if ALL_CAPS_PATTERN.search(subject):
            score -= 10
            warnings.append("Contains ALL CAPS words")

        score = max(0, min(100, score))
        spam_risk = "Low" if score >= 80 else "Medium" if score >= 60 else "High"

        results.append({
            "subject": subject,
            "score": score,
            "length": length,
            "spam_risk": spam_risk,
            "warnings": warnings
        })

    best_subject = max(results, key=lambda x: x["score"])["subject"] if results else ""
    return {"best_subject": best_subject, "results": results}

# Optional safety: if Opal accidentally prefixes discovery path
@app.post("/discovery/tools/subject-line-scorer")
def subject_line_scorer_alt(req: ToolRequest):
    return subject_line_scorer(req)
