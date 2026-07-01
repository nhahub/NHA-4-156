import os
import shutil
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from pathlib import Path
import sqlite3


class RepoVectorStore:
    def __init__(self, collection_name: str, db_path: str = "./chroma_db"):
        self.db_path = db_path
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=db_path)
        self._setup_collection()

    def collection_exists(self) -> bool:
        #True if the collection already has vectors stored.
        try:
            col = self.client.get_collection(name=self.collection_name)
            return col.count() > 0
        except Exception:
            return False

    def get_storage_context(self) -> StorageContext:
        return self.storage_context

    def get_vector_store(self) -> ChromaVectorStore:
        return self.vector_store

    def _setup_collection(self):
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    def _find_segment_folder(self) -> str | None:
        db = Path(self.db_path)
        conn = sqlite3.connect(db / "chroma.sqlite3")
        row = conn.execute("""
        SELECT s.id FROM segments s
        JOIN collections c ON s.collection = c.id
        WHERE c.name = ? AND s.scope = 'VECTOR'
        """, (self.collection_name,)).fetchone()
        conn.close()
        return row[0] if row else None

    def _delete_collection_and_disk_folder(self):
        db = Path(self.db_path)
        old_folder = self._find_segment_folder()
        print(f"Old folder: {old_folder}")

        self.client.delete_collection(name=self.collection_name)
        if old_folder:
            try:
                shutil.rmtree(db / old_folder)
                print(f"Folder Deleted successfully")
            except Exception as e:
                print(f"rmtree failed: {e}")
    def reset_collection(self):
        self._delete_collection_and_disk_folder()
        self.client = chromadb.PersistentClient(path=self.db_path)
        self._setup_collection()

    def delete_permanently(self):
        self._delete_collection_and_disk_folder()