import gc
import os
import time

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

        self.data_folder = data_folder
        self.preprocessor = RepositoryPreprocessor(output_folder=data_folder)
        self.chunker = RepositoryChunker(
            chunk_size=Settings.chunk_size,
            chunk_overlap=Settings.chunk_overlap,
        )

    def _configure_settings(self):
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50
        Settings.embed_model = RepoEmbedder().get_embed_model()

    def run(self, repo_url_or_path: str, repo_id: str) -> VectorStoreIndex:
        repo_path, was_updated = self.preprocessor.prepare(repo_url_or_path)
        vector_store = RepoVectorStore(collection_name=repo_id)
        embeddings_exist = vector_store.collection_exists()


        if embeddings_exist and not was_updated:
            return VectorStoreIndex.from_vector_store(
                vector_store=vector_store.get_vector_store()
            )


        if embeddings_exist and was_updated:
            vector_store.reset_collection()


        loader = RepositoryLoader(data_folder=repo_path)
        documents = loader.load_files()
        nodes = self.chunker.chunk_documents(documents)

        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=vector_store.get_storage_context(),
            show_progress=True,
        )

        print(f"Pipeline Done. {len(nodes)} chunks stored.")
        return index