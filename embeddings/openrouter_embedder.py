import asyncio
import concurrent.futures
import math
import os
from typing import List, Optional

import httpx
from llama_index.core.embeddings import BaseEmbedding
from pydantic import Field

# Qwen3-Embedding is instruction-aware on the *query* side only. Documents are
# embedded raw. The task string is prepended to queries in Qwen's prescribed
# `Instruct: <task>\nQuery: <text>` format, which is worth a few points of recall.
DEFAULT_TASK = (
    "Given a question about a software repository, retrieve the most relevant "
    "code snippets and documentation that answer the question."
)

# Retryable transient statuses: rate limit, and the usual upstream hiccups.
_RETRY_STATUS = {429, 500, 502, 503, 529}


class OpenRouterEmbedder(BaseEmbedding):
    """Embeddings via OpenRouter's OpenAI-compatible /embeddings endpoint.

    Defaults to Qwen3-Embedding-8B (native 4096-dim, 32K context) and truncates
    each vector to `embed_dim` dimensions Matryoshka-style, re-normalising to unit
    length afterwards. Truncation is done client-side so it works regardless of
    whether the provider honours the OpenAI `dimensions` parameter, and it keeps
    the Chroma footprint at the chosen size.

    Batch calls are fanned out: the input list is split into `request_size`-sized
    HTTP requests fired up to `max_concurrency` at a time. Qwen3-8B is a heavy
    model, so serial requests dominate ingestion time; concurrency lets the
    provider parallelise across its fleet. Transient 429/5xx are retried with
    linear backoff.
    """

    model_name: str = Field(default="qwen/qwen3-embedding-8b")
    embed_dim: int = Field(default=1024)
    api_base: str = Field(default="https://openrouter.ai/api/v1/embeddings")
    task: str = Field(default=DEFAULT_TASK)
    timeout: float = Field(default=60.0)
    request_size: int = Field(default=16)
    max_concurrency: int = Field(default=8)
    max_retries: int = Field(default=3)

    def __init__(
        self,
        model_name: str = "qwen/qwen3-embedding-8b",
        embed_dim: int = 1024,
        api_key: Optional[str] = None,
        embed_batch_size: int = 256,
        **kwargs,
    ):
        super().__init__(
            model_name=model_name,
            embed_dim=embed_dim,
            embed_batch_size=embed_batch_size,
            request_size=int(os.getenv("OPENROUTER_EMBED_REQUEST_SIZE", "16")),
            max_concurrency=int(os.getenv("OPENROUTER_EMBED_CONCURRENCY", "8")),
            **kwargs,
        )

        key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY in .env."
            )
        self._api_key = key

    @classmethod
    def class_name(cls) -> str:
        return "OpenRouterEmbedder"

    # -- vector post-processing -------------------------------------------------

    def _shrink(self, vec: List[float]) -> List[float]:
        v = vec[: self.embed_dim]
        norm = math.sqrt(sum(x * x for x in v))
        if norm > 0.0:
            v = [x / norm for x in v]
        return v

    def _instruct(self, query: str) -> str:
        return f"Instruct: {self.task}\nQuery: {query}"

    # -- HTTP -------------------------------------------------------------------

    def _payload(self, inputs: List[str]) -> dict:
        return {"model": self.model_name, "input": inputs}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}"}

    @staticmethod
    def _parse(data: dict) -> List[List[float]]:
        # OpenAI schema returns {"data": [{"embedding": [...], "index": n}, ...]};
        # sort by index defensively rather than trusting response order.
        rows = sorted(data["data"], key=lambda r: r["index"])
        return [r["embedding"] for r in rows]

    async def _post(self, client: httpx.AsyncClient, inputs: List[str]) -> List[List[float]]:
        """One embeddings request over a shared client, with backoff on transients."""
        for attempt in range(self.max_retries + 1):
            resp = await client.post(self.api_base, headers=self._headers(), json=self._payload(inputs))
            if resp.status_code in _RETRY_STATUS and attempt < self.max_retries:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return [self._shrink(v) for v in self._parse(resp.json())]
        # Exhausted retries: surface the last error to the ingest job.
        resp.raise_for_status()
        return []

    async def _aembed_many(self, texts: List[str]) -> List[List[float]]:
        """Split into request_size chunks and embed them up to max_concurrency at once."""
        if not texts:
            return []
        subs = [texts[i : i + self.request_size] for i in range(0, len(texts), self.request_size)]
        sem = asyncio.Semaphore(self.max_concurrency)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async def one(chunk: List[str]) -> List[List[float]]:
                async with sem:
                    return await self._post(client, chunk)
            results = await asyncio.gather(*(one(s) for s in subs))
        # Concatenate in submission order — gather preserves it.
        return [vec for chunk in results for vec in chunk]

    def _run_async(self, coro):
        """Run a coroutine even if called from within a running event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # A loop is already running in this thread: hand off to a worker thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    # -- BaseEmbedding interface ------------------------------------------------

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._run_async(self._aembed_many([self._instruct(query)]))[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._run_async(self._aembed_many([text]))[0]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return (await self._aembed_many([self._instruct(query)]))[0]

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return (await self._aembed_many([text]))[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._run_async(self._aembed_many(texts))

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return await self._aembed_many(texts)
