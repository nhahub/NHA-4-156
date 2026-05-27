from llama_index.core import VectorStoreIndex
from vectorstore.chroma_store import RepoVectorStore

def load_repo_index(repo_id: str) -> VectorStoreIndex:
    """Restores an index from disk without re-ingesting files"""
    store = RepoVectorStore(collection_name=repo_id)
    return VectorStoreIndex.from_vector_store(vector_store=store.get_vector_store())