import gc
import os
import time

from embeddings.embedder import RepoEmbedder
from ingestion.preprocessor import RepositoryPreprocessor
from ingestion.loader import RepositoryLoader
from ingestion.chunker import RepositoryChunker
from ingestion.exceptions import IngestionCancelled
from llama_index.core import Settings, VectorStoreIndex
from vectorstore.chroma_store import RepoVectorStore
from pathlib import Path


EMBED_BATCH_SIZE = 50


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
        provider = os.getenv("EMBEDDING_PROVIDER", "local")
        Settings.embed_model = get_embedder(provider=provider)

    @staticmethod
    def _check_stop(stop_event):
        if stop_event is not None and stop_event.is_set():
            raise IngestionCancelled()

    def run(self, repo_url_or_path: str, repo_id: str, stop_event=None) -> tuple[VectorStoreIndex, bool]:
        repo_path, was_updated = self.preprocessor.prepare(repo_url_or_path, stop_event=stop_event)

        # Checkpoint: user could have hit stop while cloning/pulling.
        self._check_stop(stop_event)

        vector_store = RepoVectorStore(collection_name=repo_id)
        embeddings_exist = vector_store.collection_exists()

        if embeddings_exist and not was_updated:
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store.get_vector_store()
            )
            return index, False

        if embeddings_exist and was_updated:
            vector_store.reset_collection()

        loader = RepositoryLoader(data_folder=repo_path)
        documents = loader.load_files()
        nodes = self.chunker.chunk_documents(documents)

        # Checkpoint: user could have hit stop during load/chunk.
        self._check_stop(stop_event)

        index = VectorStoreIndex(nodes=[], storage_context=vector_store.get_storage_context())

        total = len(nodes)
        for i in range(0, total, EMBED_BATCH_SIZE):
            # Checkpoint: this is the slow part bs (msh slow ella bs yadob check), so we check between every batch.
            self._check_stop(stop_event)

            batch = nodes[i:i + EMBED_BATCH_SIZE]
            index.insert_nodes(batch)
            print(f"Embedded {min(i + EMBED_BATCH_SIZE, total)}/{total} chunks...")

        print(f"Pipeline Done. {total} chunks stored.")
        return index, True