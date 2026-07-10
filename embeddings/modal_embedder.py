import os
from typing import List, Optional

from llama_index.core.embeddings import BaseEmbedding
from pydantic import Field


class ModalEmbedder(BaseEmbedding):
    """Embedding provider that calls a deployed Modal GPU function."""

    model_name: str = Field(default="nomic-ai/nomic-embed-text-v1.5")

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1.5",
        modal_token_id: Optional[str] = None,
        modal_token_secret: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model_name=model_name, **kwargs)

        token_id = modal_token_id or os.getenv("MODAL_TOKEN_ID")
        token_secret = modal_token_secret or os.getenv("MODAL_TOKEN_SECRET")

        if not token_id or not token_secret:
            raise RuntimeError(
                "Modal credentials not found. Set MODAL_TOKEN_ID and "
                "MODAL_TOKEN_SECRET in .env, or run `modal token set`."
            )

        import modal

        self._f = modal.Function.lookup("repo-illustrator-embedder", "embed")

    @classmethod
    def class_name(cls) -> str:
        return "ModalEmbedder"

    def _get_query_embedding(self, query: str) -> List[float]:
        result = self._f.remote([f"search_query: {query}"])
        return result[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        result = self._f.remote([f"search_document: {text}"])
        return result[0]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        result = await self._f.remote.aio([f"search_query: {query}"])
        return result[0]

    async def _aget_text_embedding(self, text: str) -> List[float]:
        result = await self._f.remote.aio([f"search_document: {text}"])
        return result[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        prefixed = [f"search_document: {t}" for t in texts]
        return self._f.remote(prefixed)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        prefixed = [f"search_document: {t}" for t in texts]
        return await self._f.remote.aio(prefixed)
