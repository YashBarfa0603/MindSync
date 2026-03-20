"""
GitHub Profile Parser — Signal Extraction Module
Fetches and analyzes a GitHub user's public profile to extract
development signals: languages, commit quality, project complexity.
"""

import requests
import os
import re
from datetime import datetime, timezone
from collections import defaultdict


def _get_headers():
    """Build request headers, optionally with a GitHub token."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def fetch_user_profile(username: str) -> dict:
    """Fetch basic user profile from GitHub API."""
    url = f"https://api.github.com/users/{username}"
    resp = requests.get(url, headers=_get_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {
        "login": data.get("login"),
        "name": data.get("name"),
        "bio": data.get("bio", ""),
        "public_repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "following": data.get("following", 0),
        "created_at": data.get("created_at"),
        "avatar_url": data.get("avatar_url"),
        "html_url": data.get("html_url"),
    }


def fetch_repos(username: str, max_repos: int = 30) -> list:
    """Fetch public repos sorted by most recently pushed."""
    url = f"https://api.github.com/users/{username}/repos"
    params = {
        "sort": "pushed",
        "direction": "desc",
        "per_page": min(max_repos, 100),
        "type": "owner",
    }
    resp = requests.get(url, headers=_get_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def extract_languages(repos: list) -> dict:
    """
    Aggregate languages across repos.
    Returns dict of {language: proportion} where proportions sum to 1.0
    Weights recent repos more heavily.
    """
    lang_scores = defaultdict(float)
    now = datetime.now(timezone.utc)

    for i, repo in enumerate(repos):
        lang = repo.get("language")
        if not lang:
            continue

        # Recency weight: more recent repos count more
        pushed_at = repo.get("pushed_at", "")
        if pushed_at:
            try:
                pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                days_ago = (now - pushed).days
                recency_weight = max(0.1, 1.0 - (days_ago / 730))  # 2 year decay
            except (ValueError, TypeError):
                recency_weight = 0.5
        else:
            recency_weight = 0.3

        # Size weight
        size = repo.get("size", 0)
        size_weight = min(1.0, max(0.1, size / 5000))

        lang_scores[lang] += recency_weight * size_weight

    # Normalize to proportions
    total = sum(lang_scores.values())
    if total == 0:
        return {}
    return {lang: round(score / total, 3) for lang, score in
            sorted(lang_scores.items(), key=lambda x: -x[1])}


def fetch_recent_commits(username: str, repos: list, max_repos: int = 5, max_commits: int = 5) -> list:
    """Fetch recent commits from top repos to assess commit quality."""
    all_commits = []
    headers = _get_headers()

    for repo in repos[:max_repos]:
        repo_name = repo.get("full_name", "")
        if not repo_name or repo.get("fork", False):
            continue

        url = f"https://api.github.com/repos/{repo_name}/commits"
        params = {"author": username, "per_page": max_commits}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                for c in resp.json():
                    msg = c.get("commit", {}).get("message", "")
                    date = c.get("commit", {}).get("author", {}).get("date", "")
                    all_commits.append({
                        "repo": repo.get("name", ""),
                        "message": msg,
                        "date": date,
                        "sha": c.get("sha", "")[:7],
                    })
        except (requests.RequestException, ValueError):
            continue

    return all_commits


def compute_commit_quality(commits: list) -> dict:
    """
    Analyze commit messages for quality signals.
    Returns quality metrics.
    """
    if not commits:
        return {"score": 0, "avg_length": 0, "conventional_pct": 0, "total_analyzed": 0}

    lengths = []
    conventional_count = 0
    # Conventional commit pattern: type(scope): message or type: message
    conv_pattern = re.compile(
        r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+?\))?:\s"
    )

    for c in commits:
        msg = c.get("message", "").split("\n")[0]  # First line only
        lengths.append(len(msg))
        if conv_pattern.match(msg):
            conventional_count += 1

    avg_length = sum(lengths) / len(lengths) if lengths else 0
    conventional_pct = conventional_count / len(commits) if commits else 0

    # Score: good length (20-72 chars ideal) + conventional commits bonus
    length_score = 0
    if 20 <= avg_length <= 72:
        length_score = 1.0
    elif 10 <= avg_length < 20 or 72 < avg_length <= 120:
        length_score = 0.6
    else:
        length_score = 0.3

    quality_score = round((0.6 * length_score + 0.4 * conventional_pct), 2)

    return {
        "score": quality_score,
        "avg_length": round(avg_length, 1),
        "conventional_pct": round(conventional_pct * 100, 1),
        "total_analyzed": len(commits),
    }


def compute_project_complexity(repos: list) -> dict:
    """
    Score project complexity based on repo attributes.
    Returns overall complexity score and per-repo details.
    """
    if not repos:
        return {"score": 0, "top_repos": [], "total_stars": 0}

    repo_details = []
    total_stars = 0

    for repo in repos:
        if repo.get("fork", False):
            continue

        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        size = repo.get("size", 0)
        has_wiki = repo.get("has_wiki", False)
        has_pages = repo.get("has_pages", False)
        description = repo.get("description", "") or ""
        topics = repo.get("topics", []) or []

        total_stars += stars

        # Complexity heuristic per repo
        complexity = 0
        complexity += min(1.0, stars / 50) * 0.25        # Stars (capped at 50)
        complexity += min(1.0, forks / 20) * 0.2         # Forks (capped at 20)
        complexity += min(1.0, size / 10000) * 0.2        # Size (capped at 10MB)
        complexity += (0.1 if has_wiki else 0)
        complexity += (0.1 if has_pages else 0)
        complexity += min(0.15, len(topics) * 0.03)       # Topics

        repo_details.append({
            "name": repo.get("name", ""),
            "description": description[:100],
            "stars": stars,
            "forks": forks,
            "language": repo.get("language", "N/A"),
            "complexity": round(complexity, 2),
            "topics": topics[:5],
            "url": repo.get("html_url", ""),
        })

    # Sort by complexity
    repo_details.sort(key=lambda x: -x["complexity"])

    # Overall score: average of top 5 repos' complexity
    top_scores = [r["complexity"] for r in repo_details[:5]]
    overall = round(sum(top_scores) / len(top_scores), 2) if top_scores else 0

    return {
        "score": overall,
        "top_repos": repo_details[:5],
        "total_stars": total_stars,
    }


def extract_skill_keywords(repos: list, languages: dict) -> list:
    """
    Extract skill keywords from repo names, descriptions, and topics.
    Combined with detected languages.
    """
    TECH_KEYWORDS = {
        "react", "angular", "vue", "svelte", "nextjs", "next.js", "remix",
        "django", "flask", "fastapi", "express", "nestjs", "spring",
        "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins",
        "github-actions", "ci/cd", "ci-cd", "aws", "gcp", "azure",
        "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch",
        "graphql", "rest", "api", "microservices", "grpc",
        "machine-learning", "deep-learning", "nlp", "computer-vision",
        "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
        "node", "nodejs", "deno", "bun",
        "git", "linux", "nginx", "apache",
        "kafka", "rabbitmq", "celery", "airflow",
        "prometheus", "grafana", "datadog",
        "streamlit", "gradio", "plotly",
        "blockchain", "web3", "solidity",
        "figma", "storybook",
        "jest", "pytest", "cypress", "selenium",
        "agile", "scrum",
        "typescript", "javascript", "python", "go", "golang", "rust",
        "java", "kotlin", "swift", "c++", "cpp", "c#", "csharp",
        "ruby", "php", "scala", "elixir", "haskell", "r",
        "html", "css", "sass", "tailwind",
        "sql", "nosql",
    }

    found_skills = set()

    # Add languages
    for lang in languages:
        found_skills.add(lang.lower())

    # Scan repo metadata
    for repo in repos:
        # Topics
        for topic in (repo.get("topics") or []):
            topic_lower = topic.lower().strip()
            if topic_lower in TECH_KEYWORDS:
                found_skills.add(topic_lower)

        # Description keywords
        desc = (repo.get("description") or "").lower()
        name = (repo.get("name") or "").lower()
        combined = f"{desc} {name}"

        for kw in TECH_KEYWORDS:
            if kw in combined:
                found_skills.add(kw)

    return sorted(found_skills)


def compute_activity_recency(repos: list) -> dict:
    """Compute how recently active the user is."""
    now = datetime.now(timezone.utc)
    push_dates = []

    for repo in repos:
        pushed_at = repo.get("pushed_at", "")
        if pushed_at:
            try:
                pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                push_dates.append(pushed)
            except (ValueError, TypeError):
                continue

    if not push_dates:
        return {"score": 0, "last_active": "Unknown", "active_months_last_year": 0}

    most_recent = max(push_dates)
    days_since = (now - most_recent).days

    # Score: 1.0 if active today, decays over 6 months
    recency_score = max(0, min(1.0, 1.0 - (days_since / 180)))

    # Count unique active months in last year
    one_year_ago = now.replace(year=now.year - 1)
    active_months = set()
    for d in push_dates:
        if d >= one_year_ago:
            active_months.add((d.year, d.month))

    return {
        "score": round(recency_score, 2),
        "last_active": most_recent.strftime("%Y-%m-%d"),
        "days_since_last_push": days_since,
        "active_months_last_year": len(active_months),
    }


def build_candidate_signal(username: str) -> dict:
    """
    Main entry point: Build complete candidate signal from GitHub profile.
    Returns structured signal data for scoring.
    """
    # Fetch data
    profile = fetch_user_profile(username)
    repos = fetch_repos(username)

    # Extract signals
    languages = extract_languages(repos)
    commits = fetch_recent_commits(username, repos)
    commit_quality = compute_commit_quality(commits)
    complexity = compute_project_complexity(repos)
    skill_keywords = extract_skill_keywords(repos, languages)
    activity = compute_activity_recency(repos)

    return {
        "username": username,
        "profile": profile,
        "languages": languages,
        "commit_quality": commit_quality,
        "project_complexity": complexity,
        "skill_keywords": skill_keywords,
        "activity": activity,
        "recent_commits": commits[:10],  # Keep top 10 for display
        "total_repos_analyzed": len(repos),
    }
