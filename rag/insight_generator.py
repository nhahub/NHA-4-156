import re
import json
from pathlib import Path

from llama_index.core.agent import ReActAgent
from rag.agent_tools import llm_provider, make_file_tools

INSIGHT_SYSTEM_PROMPT = (
    "You are a senior software developer producing an onboarding summary for a new "
    "engineer joining this codebase. You have access to these tools to explore the "
    "repository:\n"
    "- read_file: read the full content of a specific file\n"
    "- list_directory: see what files are in a directory\n"
    "- search_in_files: literal grep search across the codebase\n"
    "- get_repo_structure: overview of the repo layout\n\n"
    "Use get_repo_structure first to orient yourself, then read enough files (README, "
    "entrypoints, manifest/dependency files like requirements.txt or package.json, and "
    "the most important source files) to confidently answer. Reason and use tools as "
    "much as you need.\n\n"
    "Your FINAL message must contain ONLY a single valid JSON object - no markdown code "
    "fences, no commentary before or after it - with exactly these keys:\n\n"
    "{\n"
    '  "purpose": "2-3 sentence plain-English description of what this project does and who it is for",\n'
    '  "tech_stack": ["languages, frameworks, and key libraries actually found in the repo"],\n'
    '  "architecture": "1-2 paragraph description of how the major pieces fit together",\n'
    '  "key_files": [{"path": "relative/path", "purpose": "one sentence on what it is responsible for"}]\n'
    "}\n\n"
    "Base every field only on what you actually observed via your tools. If the repo is "
    "very small or sparse, say so honestly rather than inventing details."
)

INSIGHT_TASK_MESSAGE = (
    "Explore this repository and produce the onboarding summary. "
    "Your final reply must be ONLY the JSON object described in your instructions, nothing else."
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

    return {
        "purpose": text,
        "tech_stack": [],
        "architecture": "",
        "key_files": [],
        "parse_warning": "Agent did not return valid JSON; raw response stored in 'purpose'.",
    }


async def generate_insight(
    repo_path: str,
    provider: str = "groq",
    model_name: str = None,
) -> dict:
    path = Path(repo_path)
    llm = llm_provider(provider=provider, model_name=model_name, is_function_calling_model=False)
    tools = make_file_tools(path)

    agent = ReActAgent(
        streaming=False,
        tools=tools,
        llm=llm,
        system_prompt=INSIGHT_SYSTEM_PROMPT,
        verbose=True,
    )

    handler = agent.run(user_msg=INSIGHT_TASK_MESSAGE, max_iterations=30)
    result = await handler
    raw = result.response.content or ""

    data = _parse_agent_json(raw)
    data.setdefault("purpose", "")
    data.setdefault("tech_stack", [])
    data.setdefault("architecture", "")
    data.setdefault("key_files", [])
    return data