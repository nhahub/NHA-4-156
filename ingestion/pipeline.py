from embeddings.embedder import RepoEmbedder
from ingestion.preprocessor import RepositoryPreprocessor
from ingestion.loader import RepositoryLoader
from ingestion.chunker import RepositoryChunker
from llama_index.core import Settings, VectorStoreIndex
from vectorstore.chroma_store import RepoVectorStore
from pathlib import Path

class IngestionPipeline:
    def __init__(self, data_folder: str = "data/processed", init_global_settings: bool = False):
        if init_global_settings:
            self._configure_settings()

        self.preprocessor = RepositoryPreprocessor(output_folder=data_folder)
        self.loader = RepositoryLoader(data_folder=data_folder)
        self.chunker = RepositoryChunker(chunk_size=Settings.chunk_size, chunk_overlap=Settings.chunk_overlap)

    def _configure_settings(self):
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50
        Settings.embed_model = RepoEmbedder().get_embed_model()

    def run(self, repo_url_or_path: str, repo_id: str):
        # update loader to point exactly to the repo folder
        
        self.loader.data_folder = Path(self.preprocessor.prepare(repo_url_or_path))
        
        # load the remaining files as llamaindex documents
        documents = self.loader.load_files()
        # chunk the documents into nodes, handles code and text files accordingly
        nodes = self.chunker.chunk_documents(documents)
        # create a chromadb collection for this repo and store the nodes as vectors
        vector_store = RepoVectorStore(collection_name=repo_id)
        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=vector_store.get_storage_context(),
            show_progress=True,
        )

        return index