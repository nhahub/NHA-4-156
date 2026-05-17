from typing import List
from pathlib import Path
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode, Document


class RepositoryChunker:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk_documents(self, documents: List[Document]) -> List[BaseNode]:
        nodes = self.splitter.get_nodes_from_documents(documents)
        return nodes

    def chunk_document(self, document: Document) -> List[BaseNode]:
        return self.chunk_documents([document])

    def get_chunk_stats(self, nodes: List[BaseNode]) -> dict:
        total_tokens = sum(len(node.get_content().split()) for node in nodes)
        avg_tokens = total_tokens / len(nodes) if nodes else 0
        return {
            "total_nodes": len(nodes),
            "total_tokens": total_tokens,
            "avg_tokens_per_node": round(avg_tokens, 2),
            "chunk_size_config": self.chunk_size,
            "chunk_overlap_config": self.chunk_overlap,
        }