_PALETTE = [
    "#6366f1", "#22d3ee", "#f59e0b", "#10b981",
    "#f43f5e", "#8b5cf6", "#3b82f6", "#ec4899",
    "#14b8a6", "#f97316",
]

_LANGUAGE_COLORS = {
    "python":     "#3572A5",
    "javascript": "#f1e05a",
    "typescript": "#2b7489",
    "java":       "#b07219",
    "c":          "#555555",
    "c++":        "#f34b7d",
    "c#":         "#178600",
    "go":         "#00ADD8",
    "rust":       "#dea584",
    "ruby":       "#701516",
    "php":        "#4F5D95",
    "swift":      "#FA7343",
    "kotlin":     "#F18E33",
    "html":       "#e34c26",
    "css":        "#563d7c",
    "shell":      "#89e051",
}


def _lang_color(name: str, index: int) -> str:
    return _LANGUAGE_COLORS.get(name.lower(), _PALETTE[index % len(_PALETTE)])


def _color(index: int) -> str:
    return _PALETTE[index % len(_PALETTE)]


def build_language_pie(language_breakdown: dict) -> dict:
    if not language_breakdown:
        return {"chart_type": "pie", "title": "Language breakdown", "data": {}, "error": "No data."}

    sorted_langs = sorted(language_breakdown.items(), key=lambda x: x[1], reverse=True)

    return {
        "chart_type": "pie",
        "title": "Language breakdown",
        "data": {
            "labels":   [lang for lang, _ in sorted_langs],
            "datasets": [{
                "data":            [pct for _, pct in sorted_langs],
                "backgroundColor": [_lang_color(lang, i) for i, (lang, _) in enumerate(sorted_langs)],
            }],
        },
    }


def build_dependency_graph(dependencies: dict) -> dict:
    if not dependencies:
        return {"chart_type": "dependency_graph", "title": "Dependencies", "data": {}, "error": "No data."}

    nodes, edges = [], []
    by_ecosystem = {}
    total = 0

    for i, (ecosystem, packages) in enumerate(dependencies.items()):
        nodes.append({"id": ecosystem, "label": ecosystem.capitalize(), "type": "ecosystem", "color": _lang_color(ecosystem, i)})

        for pkg in packages:
            pkg_id = f"{ecosystem}::{pkg}"
            nodes.append({"id": pkg_id, "label": pkg, "type": "package", "ecosystem": ecosystem, "color": _color(i)})
            edges.append({"source": ecosystem, "target": pkg_id})

        by_ecosystem[ecosystem] = len(packages)
        total += len(packages)

    return {
        "chart_type": "dependency_graph",
        "title": "Dependencies",
        "data": {
            "nodes":   nodes,
            "edges":   edges,
            "summary": {"total_packages": total, "by_ecosystem": by_ecosystem},
        },
    }


def build_contributors_chart(contributors: list) -> dict:
    if not contributors:
        return {"chart_type": "contributors", "title": "Contributors", "data": {}, "error": "No data."}

    sorted_c = sorted(contributors, key=lambda c: c.get("commits", 0), reverse=True)
    top = sorted_c[:15]

    commits_bar = {
        "labels":   [c["login"] for c in top],
        #data lel commits bar chart, with background colors assigned le kol contributor
        "datasets": [{
            "label":           "Commits",
            "data":            [c.get("commits", 0) for c in top],
            "backgroundColor": [_color(i) for i in range(len(top))],
        }],
    }

    ad_contribs = [c for c in top if c.get("additions") is not None]
    additions_deletions_bar = None
    if ad_contribs:
        additions_deletions_bar = {
            "labels":   [c["login"] for c in ad_contribs],
            "datasets": [
                {"label": "Additions", "data": [c.get("additions", 0) for c in ad_contribs], "backgroundColor": "#10b981"},
                {"label": "Deletions", "data": [c.get("deletions", 0) for c in ad_contribs], "backgroundColor": "#f43f5e"},
            ],
        }

    return {
        "chart_type": "contributors",
        "title": "Contributors",
        "data": {
            "commits_bar":             commits_bar,
            "additions_deletions_bar": additions_deletions_bar,
            "table":                   sorted_c,
        },
    }


def build_chart_data(repo_insights: dict) -> dict:
    return {
        "charts": {
            "overview":           build_overview(repo_insights),
            "language_breakdown": build_language_pie(repo_insights.get("language_breakdown", {})),
            "dependencies":       build_dependency_graph(repo_insights.get("dependencies", {})),
            "contributors":       build_contributors_chart(repo_insights.get("contributors", [])),
            "analytics":          build_analytics(repo_insights),
        }
    }

def build_overview(repo_insights: dict) -> dict:
    analysis = repo_insights.get("analysis", {})
    return {
        "chart_type": "overview",
        "title": "Overview",
        "data": {
            "summary":     repo_insights.get("summary", ""),
            "description": analysis.get("github_description", ""),
            "health":      analysis.get("health", {}),
            "metrics":     analysis.get("metrics", {}),
            "tech_stack":  repo_insights.get("language_breakdown", {}),
        },
    }


def build_analytics(repo_insights: dict) -> dict:
    analysis = repo_insights.get("analysis", {})
    return {
        "chart_type": "analytics",
        "title": "Codebase Analytics",
        "data": analysis.get("analytics", {}),
    }