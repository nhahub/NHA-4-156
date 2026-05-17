from pathlib import Path
from typing import List
from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document


class RepositoryLoader:
    def __init__(self, data_folder: str = "data/processed"):
        self.data_folder = Path(data_folder)
        if not self.data_folder.exists():
            raise ValueError(f"Data folder not found: {data_folder}")

    def load_files(self) -> List[Document]:
        reader = SimpleDirectoryReader(
            input_dir=str(self.data_folder),
            recursive=True,
            filename_as_id=True,
        )
        documents = reader.load_data()

        for doc in documents:
            doc.metadata["repo_name"] = self.data_folder.name

        print(f"Loaded {len(documents)} documents from {self.data_folder}")
        return documents