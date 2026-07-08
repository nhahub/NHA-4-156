import re
import os
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from llama_index.core.agent import ReActAgent
from rag.agent_tools import llm_provider, make_file_tools


CHARTS_SYSTEM_PROMPT = (
    "You are a senior software developer analyzing a code repository. "
    "Use get_repo_structure first, then read dependency files "
    "(requirements.txt, package.json, pyproject.toml, Cargo.toml, go.mod, etc.) "
    "to answer accurately.\n\n"
    "Your FINAL message must contain ONLY a single valid JSON object with exactly these keys:\n\n"
    "{\n"
    "  \"summary\": \"One clear paragraph describing what this project does and how it works.\",\n"
    "  \"language_breakdown\": {\"Python\": 65, \"JavaScript\": 30, \"HTML\": 5},\n"
    "  \"dependencies\": {\"python\": [\"fastapi\", \"pydantic\"], \"javascript\": [\"react\"]}\n"
    "}\n\n"
    "Rules:\n"
    "- summary: 3-5 sentences, plain language, what the project does and its main components\n"
    "- language_breakdown: language names as keys, integer percentages as values, must sum to 100\n"
    "- dependencies: ecosystem name (lowercase) as keys, list of package name strings as values, no version numbers\n"
    "- only include what you actually found in the files"
)

CHARTS_TASK_MESSAGE = (
    "Explore this repository and return the JSON object with summary, language_breakdown and dependencies. "
    "Your final reply must be ONLY the JSON object, nothing else."
)


def _parse_agent_json(raw_text: str) -> dict:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {}

#returns dictionary 
def _normalize_language_breakdown(raw: dict) -> dict:
    if not isinstance(raw, dict) or not raw:
        return {}

    clean = {k: int(v) for k, v in raw.items() if isinstance(v, (int, float)) and int(v) > 0}
    if not clean:
        return {}

    total = sum(clean.values())
    normalized = {k: round(v / total * 100) for k, v in clean.items()}

    diff = 100 - sum(normalized.values())
    if diff != 0:
        largest = max(normalized, key=normalized.get)
        normalized[largest] += diff

    return normalized


def _parse_github_owner_repo(repo_url: str):
    url = repo_url.strip()

    ssh = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh:
        return ssh.group(1), ssh.group(2)

    parsed = urlparse(url)
    if "github.com" not in (parsed.netloc or ""):
        return None

    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None

    return parts[0], parts[1].replace(".git", "")


def _enrich_with_stats(owner: str, repo: str, headers: dict, contributors: list):
    stats_url = f"https://api.github.com/repos/{owner}/{repo}/stats/contributors"

    for _ in range(2):
        try:
            resp = requests.get(stats_url, headers=headers, timeout=20)
            if resp.status_code == 202:
                time.sleep(3)
                continue
            if resp.status_code != 200:
                return

            stats = resp.json()
            if not isinstance(stats, list):
                return

            stats_map = {}
            for entry in stats:
                author = entry.get("author") or {}
                login = author.get("login", "")
                if not login:
                    continue
                total_add = sum(w.get("a", 0) for w in entry.get("weeks", []))
                total_del = sum(w.get("d", 0) for w in entry.get("weeks", []))
                stats_map[login] = (total_add, total_del)

            for c in contributors:
                if c["login"] in stats_map:
                    c["additions"] = stats_map[c["login"]][0]
                    c["deletions"] = stats_map[c["login"]][1]
            return

        except requests.RequestException:
            return

#returns list of contributors with their stats
def fetch_contributors(repo_url: str) -> list:
    owner_repo = _parse_github_owner_repo(repo_url)
    if owner_repo is None:
        return []

    owner, repo = owner_repo
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/contributors",
            headers=headers,
            params={"per_page": 30, "anon": "false"},
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        contributors = []
        for c in resp.json():
            if c.get("type") == "Bot":
                continue
            contributors.append({
                "login":       c.get("login", "unknown"),
                "avatar_url":  c.get("avatar_url", ""),
                "profile_url": c.get("html_url", ""),
                "commits":     c.get("contributions", 0),
                "additions":   None,
                "deletions":   None,
            })

        _enrich_with_stats(owner, repo, headers, contributors[:10])
        return contributors

    except requests.RequestException:
        return []


async def build_repo_insights(repo_id: str, repo_url: str, provider: str = "groq", model_name: str = None) -> dict:
    repo_path = Path("data/processed") / repo_id

    llm = llm_provider(provider=provider, model_name=model_name, is_function_calling_model=False)
    tools = make_file_tools(repo_path)

    agent = ReActAgent(
        streaming=False,
        tools=tools,
        llm=llm,
        system_prompt=CHARTS_SYSTEM_PROMPT,
        verbose=True,
    )

    handler = agent.run(user_msg=CHARTS_TASK_MESSAGE)
    result = await handler
    raw = result.response.content or ""

    parsed = _parse_agent_json(raw)

    language_breakdown = _normalize_language_breakdown(parsed.get("language_breakdown", {}))

    dependencies = {}
    raw_deps = parsed.get("dependencies", {})
    if isinstance(raw_deps, dict):
        for ecosystem, packages in raw_deps.items():
            if isinstance(packages, list):
                dependencies[str(ecosystem).lower()] = [str(p) for p in packages]

    summary = str(parsed.get("summary", "")).strip()

    contributors = fetch_contributors(repo_url)

    # static analysis + github metrics + health score
    owner_repo = _parse_github_owner_repo(repo_url)
    analysis = {}
    if owner_repo:
        from insights.analyzer import analyze_repo
        analysis = analyze_repo(repo_id, owner_repo[0], owner_repo[1], len(contributors))

    return {
        "summary":            summary,
        "language_breakdown": language_breakdown,
        "dependencies":       dependencies,
        "contributors":       contributors,
        "analysis":           analysis,
    }