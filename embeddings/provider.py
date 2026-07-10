import os
from llama_index.core.embeddings import BaseEmbedding


def get_embedder(provider: str = "local", model_name: str = None) -> BaseEmbedding:
    if provider == "local":
        from embeddings.embedder import RepoEmbedder
        name = model_name or "nomic-ai/nomic-embed-text-v1.5"
        return RepoEmbedder(model_name=name).get_embed_model()

    elif provider == "modal":
        from embeddings.modal_embedder import ModalEmbedder
        name = model_name or "nomic-ai/nomic-embed-text-v1.5"
        return ModalEmbedder(model_name=name)

    raise ValueError(
        f"Unsupported embedding provider '{provider}'. "
        f"Must be one of: local, modal"
    )
