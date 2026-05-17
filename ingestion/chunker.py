from typing import List
from pathlib import Path
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.core.schema import BaseNode, Document

CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".cs"}

class RepositoryChunker:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.code_splitter = CodeSplitter(
            language="python",       
            chunk_lines=40,
            chunk_lines_overlap=5,
            max_chars=1500,
        )
        self.text_splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk_documents(self, documents: List[Document]) -> List[BaseNode]:
        code_docs, text_docs = [], []
        for doc in documents:
            ext = Path(doc.metadata.get("file_path", "")).suffix
            if ext in CODE_EXTENSIONS:
                code_docs.append(doc)
            else:
                text_docs.append(doc)

        nodes = []
        if code_docs:
            nodes += self.code_splitter.get_nodes_from_documents(code_docs)
        if text_docs:
            nodes += self.text_splitter.get_nodes_from_documents(text_docs)

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