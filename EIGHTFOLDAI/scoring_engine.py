"""
Scoring Engine — Candidate-to-JD Matching
Uses sentence-transformers embeddings + cosine similarity
combined with GitHub signal scores for overall candidate scoring.
"""

import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import functools

# ─── Model (lazy-loaded, cached) ─────────────────────────────────────────────

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ─── Embedding Helpers ───────────────────────────────────────────────────────

@functools.lru_cache(maxsize=512)
def _embed_text(text: str) -> tuple:
    """Embed a single text string. Returns tuple for caching."""
    model = _get_model()
    vec = model.encode([text])[0]
    return tuple(vec.tolist())


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed multiple texts."""
    model = _get_model()
    return model.encode(texts)


# ─── Skill-level Matching ────────────────────────────────────────────────────

def compute_skill_match(candidate_skills: List[str], jd_skills: List[str]) -> Dict:
    """
    Compute per-skill and overall match between candidate and JD skills.
    Uses embedding similarity for fuzzy matching.

    Returns:
        {
            "overall_score": float (0-100),
            "matched_skills": [(jd_skill, best_candidate_match, similarity)],
            "missing_skills": [jd_skill],
            "extra_skills": [candidate_skill],  # candidate has but JD doesn't need
            "per_skill_scores": {jd_skill: {"match": str, "score": float}},
        }
    """
    if not jd_skills:
        return {
            "overall_score": 0,
            "matched_skills": [],
            "missing_skills": [],
            "extra_skills": candidate_skills,
            "per_skill_scores": {},
        }

    if not candidate_skills:
        return {
            "overall_score": 0,
            "matched_skills": [],
            "missing_skills": jd_skills,
            "extra_skills": [],
            "per_skill_scores": {s: {"match": None, "score": 0} for s in jd_skills},
        }

    # Embed all skills
    jd_embeddings = embed_texts(jd_skills)
    candidate_embeddings = embed_texts(candidate_skills)

    # Compute similarity matrix: (num_jd_skills x num_candidate_skills)
    sim_matrix = cosine_similarity(jd_embeddings, candidate_embeddings)

    matched_skills = []
    missing_skills = []
    per_skill_scores = {}
    match_threshold = 0.55  # Skills with similarity above this are considered matched

    for i, jd_skill in enumerate(jd_skills):
        best_idx = int(np.argmax(sim_matrix[i]))
        best_score = float(sim_matrix[i][best_idx])
        best_candidate_skill = candidate_skills[best_idx]

        if best_score >= match_threshold:
            matched_skills.append((jd_skill, best_candidate_skill, round(best_score, 3)))
            per_skill_scores[jd_skill] = {
                "match": best_candidate_skill,
                "score": round(best_score * 100, 1),
                "status": "matched" if best_score >= 0.75 else "partial",
            }
        else:
            missing_skills.append(jd_skill)
            per_skill_scores[jd_skill] = {
                "match": None,
                "score": round(best_score * 100, 1),
                "status": "missing",
            }

    # Extra skills: candidate skills not closely matched to any JD skill
    matched_candidate_skills = {m[1] for m in matched_skills}
    extra_skills = [s for s in candidate_skills if s not in matched_candidate_skills]

    # Overall score: weighted by match quality
    if jd_skills:
        scores = [per_skill_scores[s]["score"] for s in jd_skills]
        overall = round(sum(scores) / len(scores), 1)
    else:
        overall = 0

    return {
        "overall_score": overall,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "extra_skills": extra_skills,
        "per_skill_scores": per_skill_scores,
    }


# ─── GitHub Signal Score ─────────────────────────────────────────────────────

def compute_github_signal_score(candidate_signal: Dict) -> Dict:
    """
    Compute a composite score from GitHub signals.
    Returns breakdown and overall score (0-100).
    """
    commit_quality = candidate_signal.get("commit_quality", {}).get("score", 0)
    project_complexity = candidate_signal.get("project_complexity", {}).get("score", 0)
    activity_recency = candidate_signal.get("activity", {}).get("score", 0)

    # Weights
    weights = {
        "commit_quality": 0.3,
        "project_complexity": 0.4,
        "activity_recency": 0.3,
    }

    components = {
        "commit_quality": round(commit_quality * 100, 1),
        "project_complexity": round(project_complexity * 100, 1),
        "activity_recency": round(activity_recency * 100, 1),
    }

    overall = round(
        weights["commit_quality"] * components["commit_quality"] +
        weights["project_complexity"] * components["project_complexity"] +
        weights["activity_recency"] * components["activity_recency"],
        1
    )

    return {
        "overall_score": overall,
        "components": components,
        "weights": weights,
    }


# ─── Overall Score ───────────────────────────────────────────────────────────

def compute_overall_score(
    skill_match_score: float,
    github_signal_score: float,
    skill_weight: float = 0.6,
    github_weight: float = 0.4,
) -> Dict:
    """
    Compute final overall candidate score.
    Skill match is weighted more heavily as it directly measures JD fit.
    """
    overall = round(
        skill_weight * skill_match_score +
        github_weight * github_signal_score,
        1
    )

    return {
        "overall_score": overall,
        "skill_match_contribution": round(skill_weight * skill_match_score, 1),
        "github_signal_contribution": round(github_weight * github_signal_score, 1),
        "weights": {"skill_match": skill_weight, "github_signal": github_weight},
    }


# ─── Multi-Candidate Ranking ────────────────────────────────────────────────

def rank_candidates(candidates_data: List[Dict], jd_parsed: Dict) -> List[Dict]:
    """
    Score and rank multiple candidates against a JD.

    Args:
        candidates_data: list of dicts from build_candidate_signal()
        jd_parsed: parsed JD from extract_skills_from_jd()

    Returns:
        Ranked list of {candidate, skill_match, github_score, overall, rank}
    """
    jd_skills = jd_parsed.get("all_skills", [])
    results = []

    for candidate in candidates_data:
        candidate_skills = candidate.get("skill_keywords", [])

        # Skill matching
        skill_result = compute_skill_match(candidate_skills, jd_skills)

        # GitHub signals
        github_result = compute_github_signal_score(candidate)

        # Overall
        overall_result = compute_overall_score(
            skill_result["overall_score"],
            github_result["overall_score"],
        )

        results.append({
            "username": candidate.get("username", "unknown"),
            "profile": candidate.get("profile", {}),
            "skill_match": skill_result,
            "github_score": github_result,
            "overall": overall_result,
        })

    # Sort by overall score descending
    results.sort(key=lambda x: -x["overall"]["overall_score"])

    # Assign ranks
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results
