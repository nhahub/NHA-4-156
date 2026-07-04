from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[RepoEmbedder] Using device: {device}")
if torch.cuda.is_available():
    print(f"[RepoEmbedder] GPU: {torch.cuda.get_device_name(0)}")

class RepoEmbedder:
    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5"):
        self.model_name = model_name
        self.embedder = HuggingFaceEmbedding(
            model_name=model_name,
            trust_remote_code=True,
            text_instruction="search_document: ",
            query_instruction="search_query: ",
            device=device,
            )

    def get_embed_model(self):
        return self.embedder