import os
from llama_index.core.embeddings import BaseEmbedding


def get_embedder(provider: str = "local", model_name: str = None) -> BaseEmbedding:
    if provider == "local":
        from embeddings.embedder import RepoEmbedder
        name = model_name or "nomic-ai/nomic-embed-text-v1.5"
        return RepoEmbedder(model_name=name).get_embed_model()

    elif provider == "openrouter":
        from embeddings.openrouter_embedder import OpenRouterEmbedder
        name = model_name or "qwen/qwen3-embedding-8b"
        return OpenRouterEmbedder(model_name=name, embed_dim=1024)

    raise ValueError(
        f"Unsupported embedding provider '{provider}'. "
        f"Must be one of: local, openrouter"
    )
