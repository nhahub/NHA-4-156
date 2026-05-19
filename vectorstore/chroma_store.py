import chromadb 
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext

class RepoVectorStore:
    def __init__(self, collection_name : str,  db_path: str = "./chroma_db"):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    def get_storage_context(self) -> StorageContext:
        return self.storage_context
        # this is used in index construction to know where to store the vectors
    
    def delete_collection(self):
        self.client.delete_collection(name=self.collection.name)

    def get_vector_store(self) -> ChromaVectorStore:
        return self.vector_store
        # this is used for retrieval after the index is built
