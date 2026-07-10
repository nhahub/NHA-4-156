import os
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")

print(f"Using model: {model}")
print(f"API key set: {bool(api_key)}")

resp = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 50,
    },
)

print(f"\nStatus: {resp.status_code}")
print(f"Response: {resp.text[:1000]}")
