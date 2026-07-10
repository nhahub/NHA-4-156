import modal

app = modal.App("repo-illustrator-embedder")

image = (
    modal.Image.debian_slim()
    .pip_install(
        "sentence-transformers",
        "torch",
        "torchvision",
        "einops",
        "numpy",
    )
)


@app.function(
    image=image,
    gpu="T4",
    container_idle_timeout=300,
    keep_warm=1,
    timeout=120,
)
def embed(texts: list[str]) -> list[list[float]]:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        "nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True
    )
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
