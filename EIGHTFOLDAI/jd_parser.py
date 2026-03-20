"""
Job Description Parser — Skill Extraction Module
Extracts required and preferred skills from a job description
using a curated skill taxonomy and keyword matching.
"""

import re
from typing import Dict, List


# ─── Skill Taxonomy ──────────────────────────────────────────────────────────
# Organized by category for better matching and explainability

SKILL_TAXONOMY = {
    # Programming Languages
    "python": ["python", "py", "python3"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "go": ["golang", "go lang", " go "],
    "rust": ["rust"],
    "java": ["java ","java,", "java.", "java/"],
    "kotlin": ["kotlin"],
    "swift": ["swift"],
    "c++": ["c++", "cpp", "c plus plus"],
    "c#": ["c#", "csharp", "c sharp", ".net"],
    "ruby": ["ruby"],
    "php": ["php"],
    "scala": ["scala"],
    "r": [" r ", "r,", " r,"],
    "sql": ["sql", "structured query language"],
    "bash": ["bash", "shell scripting", "shell script"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],

    # Frontend Frameworks
    "react": ["react", "reactjs", "react.js"],
    "angular": ["angular", "angularjs"],
    "vue": ["vue", "vuejs", "vue.js"],
    "svelte": ["svelte"],
    "next.js": ["next.js", "nextjs", "next js"],
    "remix": ["remix"],

    # Backend Frameworks
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi", "fast api"],
    "express": ["express", "expressjs", "express.js"],
    "nestjs": ["nestjs", "nest.js"],
    "spring": ["spring", "spring boot", "springboot"],

    # Databases
    "postgresql": ["postgresql", "postgres", "psql"],
    "mysql": ["mysql", "my sql"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "elasticsearch": ["elasticsearch", "elastic search", "elk"],
    "cassandra": ["cassandra"],
    "dynamodb": ["dynamodb", "dynamo db"],

    # DevOps & Infrastructure
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "terraform": ["terraform", "iac", "infrastructure as code"],
    "ansible": ["ansible"],
    "ci/cd": ["ci/cd", "ci cd", "continuous integration", "continuous deployment"],
    "github actions": ["github actions"],
    "jenkins": ["jenkins"],
    "argocd": ["argocd", "argo cd"],

    # Cloud Platforms
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud"],
    "azure": ["azure", "microsoft azure"],

    # ML & Data
    "machine learning": ["machine learning", "ml "],
    "deep learning": ["deep learning", "dl "],
    "pytorch": ["pytorch", "torch"],
    "tensorflow": ["tensorflow", "tf "],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "nlp": ["nlp", "natural language processing"],
    "computer vision": ["computer vision", "cv "],
    "transformers": ["transformers", "bert", "gpt"],
    "mlflow": ["mlflow", "ml flow"],
    "airflow": ["airflow", "air flow"],
    "spark": ["spark", "pyspark", "apache spark"],

    # Messaging & Queues
    "kafka": ["kafka"],
    "rabbitmq": ["rabbitmq", "rabbit mq"],

    # API & Architecture
    "rest api": ["rest", "restful", "rest api"],
    "graphql": ["graphql", "graph ql"],
    "grpc": ["grpc", "g rpc"],
    "microservices": ["microservices", "micro services", "micro-services"],

    # Monitoring & Observability
    "prometheus": ["prometheus"],
    "grafana": ["grafana"],
    "datadog": ["datadog"],

    # Testing
    "jest": ["jest"],
    "pytest": ["pytest"],
    "cypress": ["cypress"],
    "selenium": ["selenium"],

    # Other Tools
    "git": ["git ", "git,", "version control"],
    "linux": ["linux", "unix"],
    "nginx": ["nginx"],
    "webpack": ["webpack"],
    "vite": ["vite"],
}

SKILL_CATEGORIES = {
    "Programming Languages": [
        "python", "javascript", "typescript", "go", "rust", "java", "kotlin",
        "swift", "c++", "c#", "ruby", "php", "scala", "r", "sql", "bash", "html", "css"
    ],
    "Frontend": [
        "react", "angular", "vue", "svelte", "next.js", "remix", "html", "css"
    ],
    "Backend": [
        "django", "flask", "fastapi", "express", "nestjs", "spring"
    ],
    "Databases": [
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra", "dynamodb"
    ],
    "DevOps & Cloud": [
        "docker", "kubernetes", "terraform", "ansible", "ci/cd", "github actions",
        "jenkins", "argocd", "aws", "gcp", "azure"
    ],
    "ML & Data": [
        "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
        "pandas", "numpy", "nlp", "computer vision", "transformers", "mlflow", "airflow", "spark"
    ],
    "Architecture & APIs": [
        "rest api", "graphql", "grpc", "microservices", "kafka", "rabbitmq"
    ],
    "Testing": ["jest", "pytest", "cypress", "selenium"],
    "Other": ["git", "linux", "nginx", "webpack", "vite", "prometheus", "grafana", "datadog"],
}


def _find_section(text: str, headers: list) -> str:
    """Try to extract text under specific section headers."""
    text_lower = text.lower()
    for header in headers:
        pattern = re.compile(
            rf"(?:^|\n)\s*(?:\*\*)?{re.escape(header)}(?:\*\*)?[:\s]*\n(.*?)(?=\n\s*(?:\*\*)?(?:{'|'.join(re.escape(h) for h in headers)})|$)",
            re.IGNORECASE | re.DOTALL
        )
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def extract_skills_from_jd(text: str) -> Dict:
    """
    Extract skills from a job description using taxonomy matching.
    Returns required skills, preferred skills, and role title.
    """
    text_lower = f" {text.lower()} "  # Pad for boundary matching

    # Try to identify role title
    role_title = ""
    title_patterns = [
        r"(?:^|\n)\s*(.+?(?:engineer|developer|architect|manager|analyst|scientist|designer))\s*(?:\n|—|–|-)",
        r"(?:role|position|title)[:\s]+(.+?)(?:\n|$)",
    ]
    for pattern in title_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            role_title = match.group(1).strip()[:100]
            break

    # Split into required vs preferred sections
    required_section = _find_section(text, [
        "requirements", "required", "must have", "what you'll need",
        "qualifications", "what we're looking for", "you have", "you bring"
    ])
    preferred_section = _find_section(text, [
        "nice to have", "preferred", "bonus", "plus", "ideally",
        "nice-to-have", "good to have", "additional"
    ])

    # If no sections found, treat entire text as requirements
    if not required_section and not preferred_section:
        required_section = text

    # Match skills
    required_skills = _match_skills(required_section if required_section else text)
    preferred_skills = _match_skills(preferred_section) if preferred_section else []

    # Remove duplicates: if a skill is in required, don't list in preferred
    preferred_skills = [s for s in preferred_skills if s not in required_skills]

    # Categorize
    categorized = _categorize_skills(required_skills + preferred_skills)

    return {
        "role_title": role_title,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "all_skills": required_skills + preferred_skills,
        "categorized_skills": categorized,
    }


def _match_skills(text: str) -> List[str]:
    """Match skills from text using taxonomy."""
    if not text:
        return []

    text_lower = f" {text.lower()} "
    matched = []

    for skill, aliases in SKILL_TAXONOMY.items():
        for alias in aliases:
            if alias.lower() in text_lower:
                if skill not in matched:
                    matched.append(skill)
                break

    return matched


def _categorize_skills(skills: List[str]) -> Dict[str, List[str]]:
    """Categorize detected skills by domain."""
    result = {}
    for category, category_skills in SKILL_CATEGORIES.items():
        found = [s for s in skills if s in category_skills]
        if found:
            result[category] = found
    return result


def get_skill_text_for_embedding(parsed_jd: dict) -> str:
    """
    Build a text representation of the JD skills for embedding.
    Used by the scoring engine for semantic matching.
    """
    parts = []
    if parsed_jd.get("role_title"):
        parts.append(parsed_jd["role_title"])

    required = parsed_jd.get("required_skills", [])
    if required:
        parts.append("Required skills: " + ", ".join(required))

    preferred = parsed_jd.get("preferred_skills", [])
    if preferred:
        parts.append("Preferred skills: " + ", ".join(preferred))

    return ". ".join(parts)


def extract_skills_from_resume(text: str) -> Dict:
    """
    Extract all technical and soft skills from resume text.
    Returns a structured result matching the hackathon prompt format:
    {"skills": ["Python", "Machine Learning", ...], "categorized": {...}}

    This mirrors the LLM prompt:
      System: You are a skill extraction engine. Extract all technical and soft
      skills from the provided resume text. Return ONLY a valid JSON array of strings.
    """
    if not text or not text.strip():
        return {"skills": [], "categorized": {}, "skill_count": 0}

    # Use the same taxonomy matching as JD parser
    matched_skills = _match_skills(text)

    # Also extract soft skills via keyword matching
    SOFT_SKILLS = {
        "leadership": ["leadership", "led a team", "team lead", "managed a team"],
        "communication": ["communication", "presented", "stakeholder", "cross-functional"],
        "problem solving": ["problem solving", "problem-solving", "analytical", "critical thinking"],
        "teamwork": ["teamwork", "collaboration", "collaborative", "team player"],
        "project management": ["project management", "agile", "scrum", "kanban", "sprint"],
        "mentoring": ["mentoring", "mentored", "coaching", "trained"],
        "time management": ["time management", "deadline", "prioritization"],
    }

    text_lower = f" {text.lower()} "
    for skill, aliases in SOFT_SKILLS.items():
        for alias in aliases:
            if alias in text_lower:
                if skill not in matched_skills:
                    matched_skills.append(skill)
                break

    categorized = _categorize_skills(matched_skills)

    return {
        "skills": matched_skills,
        "categorized": categorized,
        "skill_count": len(matched_skills),
    }
