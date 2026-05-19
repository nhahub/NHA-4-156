from embeddings.embedder import RepoEmbedder
from ingestion.preprocessor import RepositoryPreprocessor
from ingestion.loader import RepositoryLoader
from ingestion.chunker import RepositoryChunker
from llama_index.core import Settings


class IngestionPipeline:
    def __init__(self, data_folder: str = "data/processed"):
        self._configure_settings()

        self.preprocessor = RepositoryPreprocessor(output_folder=data_folder)
        self.loader = RepositoryLoader(data_folder=data_folder)
        self.chunker = RepositoryChunker(chunk_size=Settings.chunk_size, chunk_overlap=Settings.chunk_overlap)

    def _configure_settings(self):
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50
        Settings.embed_model = RepoEmbedder().get_embed_model()

    def run(self, repo_url_or_path: str):
        self.preprocessor.prepare(repo_url_or_path)
        documents = self.loader.load_files()
        nodes = self.chunker.chunk_documents(documents)
        return nodes