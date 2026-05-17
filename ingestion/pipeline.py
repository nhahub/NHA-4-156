from ingestion.preprocessor import RepositoryPreprocessor
from ingestion.loader import RepositoryLoader
from ingestion.chunker import RepositoryChunker

class IngestionPipeline:
    def __init__(self, data_folder: str = "data/processed"):
        self.preprocessor = RepositoryPreprocessor(output_folder=data_folder)
        self.loader = RepositoryLoader(data_folder=data_folder)
        self.chunker = RepositoryChunker()

    def run(self, repo_url_or_path: str):
        self.preprocessor.prepare(repo_url_or_path)
        documents = self.loader.load_files()
        nodes = self.chunker.chunk_documents(documents)
        return nodes