import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".vue",
}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".vscode", ".idea", "target", "out", "bin", "obj",
}

TEST_MARKERS = ("test_", "_test.", ".test.", ".spec.", "tests/", "test/", "__tests__")


def _github_headers():
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_repo_info(owner: str, repo: str) -> dict:
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=_github_headers(), timeout=15,
        )
        if resp.status_code != 200:
            return {}
        d = resp.json()
        return {
            "stars": d.get("stargazers_count", 0),
            "open_issues": d.get("open_issues_count", 0),
            "pushed_at": d.get("pushed_at", ""),
            "description": d.get("description") or "",
        }
    except requests.RequestException:
        return {}


def fetch_closed_issues_count(owner: str, repo: str) -> int:
    try:
        resp = requests.get(
            "https://api.github.com/search/issues",
            headers=_github_headers(),
            params={"q": f"repo:{owner}/{repo} type:issue state:closed", "per_page": 1},
            timeout=15,
        )
        if resp.status_code != 200:
            return 0
        return resp.json().get("total_count", 0)
    except requests.RequestException:
        return 0


def analyze_files(repo_path: Path) -> dict:
    total_files = 0
    code_files = 0
    test_files = 0
    lines_of_code = 0
    todos = 0
    file_sizes = []  # for code files

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            total_files += 1
            path = Path(root) / f
            rel = str(path.relative_to(repo_path)).replace("\\", "/")

            if path.suffix not in CODE_EXTENSIONS:
                continue
            code_files += 1

            if any(m in rel.lower() or m in f.lower() for m in TEST_MARKERS):
                test_files += 1

            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            loc = text.count("\n") + 1
            lines_of_code += loc
            todos += len(re.findall(r"\b(TODO|FIXME)\b", text))
            file_sizes.append((rel, loc))

    # most complex files : top 5 by lines of code
    file_sizes.sort(key=lambda x: x[1], reverse=True)
    complex_files = []
    for rel, loc in file_sizes[:5]:
        level = "High" if loc > 400 else "Med" if loc > 150 else "Low"
        complex_files.append({"file": rel, "lines": loc, "level": level})

    has_ci = (repo_path / ".github" / "workflows").exists()

    readme_len = 0
    for name in ("README.md", "README.rst", "README.txt", "readme.md"):
        p = repo_path / name
        if p.exists():
            try:
                readme_len = len(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
            break
    has_docs_folder = (repo_path / "docs").exists()

    return {
        "total_files": total_files,
        "code_files": code_files,
        "test_files": test_files,
        "lines_of_code": lines_of_code,
        "todos": todos,
        "complex_files": complex_files,
        "has_ci": has_ci,
        "readme_len": readme_len,
        "has_docs_folder": has_docs_folder,
    }


def hot_files(raw_repo_path: Path, limit: int = 5) -> list:
    try:
        out = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:"],
            cwd=raw_repo_path, capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return []

    counts = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        counts[line] = counts.get(line, 0) + 1

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"file": f, "changes": c} for f, c in ranked[:limit]]


def _days_since(iso_date: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def compute_health_score(repo_info: dict, closed_issues: int, contributors_count: int, files: dict) -> dict:
    stars = repo_info.get("stars", 0)
    stars_score = min(stars / 1000, 1.0) * 20 #20%

    days = _days_since(repo_info.get("pushed_at", "")) #last Commit
    if days <= 7:
        recency_score = 20.0
    elif days >= 365:
        recency_score = 0.0
    else:
        recency_score = (1 - (days - 7) / 358) * 20

    open_issues = repo_info.get("open_issues", 0)
    total_issues = open_issues + closed_issues
    ratio_score = (closed_issues / total_issues if total_issues > 0 else 0.5) * 15

    ci_score = 10.0 if files.get("has_ci") else 0.0

    test_score = min(files.get("test_files", 0) / 10, 1.0) * 15

    contrib_score = min(contributors_count / 10, 1.0) * 10

    doc_score = 0.0
    readme_len = files.get("readme_len", 0)
    if readme_len > 3000:
        doc_score += 7
    elif readme_len > 500:
        doc_score += 4
    elif readme_len > 0:
        doc_score += 2
    if files.get("has_docs_folder"):
        doc_score += 3
    doc_score = min(doc_score, 10.0)

    total = round(stars_score + recency_score + ratio_score + ci_score + test_score + contrib_score + doc_score)

    return {
        "score": total,
        "breakdown": {
            "stars": round(stars_score, 1),
            "recency": round(recency_score, 1),
            "issue_ratio": round(ratio_score, 1),
            "ci_cd": round(ci_score, 1),
            "tests": round(test_score, 1),
            "contributors": round(contrib_score, 1),
            "documentation": round(doc_score, 1),
        },
    }


def analyze_repo(repo_id: str, owner: str, repo: str, contributors_count: int) -> dict:
    processed_path = Path("data/processed") / repo_id
    raw_path = Path("data/raw") / repo_id

    files = analyze_files(processed_path)
    repo_info = fetch_repo_info(owner, repo)
    closed_issues = fetch_closed_issues_count(owner, repo)
    health = compute_health_score(repo_info, closed_issues, contributors_count, files)

    code_files = files["code_files"] or 1
    coverage_estimate = round(min(files["test_files"] / code_files, 1.0) * 100)

    days = _days_since(repo_info.get("pushed_at", ""))
    if days >= 9999:
        last_commit = "unknown"
    elif days == 0:
        last_commit = "today"
    elif days < 30:
        last_commit = f"{int(days)}d ago"
    elif days < 365:
        last_commit = f"{int(days // 30)}mo ago"
    else:
        last_commit = f"{int(days // 365)}y ago"

    return {
        "health": health,
        "metrics": {
            "stars": repo_info.get("stars", 0),
            "open_issues": repo_info.get("open_issues", 0),
            "closed_issues": closed_issues,
            "last_commit": last_commit,
            "contributors": contributors_count,
        },
        "analytics": {
            "total_files": files["total_files"],
            "lines_of_code": files["lines_of_code"],
            "todos": files["todos"],
            "test_coverage_estimate": coverage_estimate,
            "complex_files": files["complex_files"],
            "hot_files": hot_files(raw_path),
        },
        "github_description": repo_info.get("description", ""),
    }