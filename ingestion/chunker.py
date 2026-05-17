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
    

# el code elly ana 3awzah:
# from typing import List
# from pathlib import Path
# from collections import defaultdict
# from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
# from llama_index.core.schema import BaseNode, Document

# CODE_EXTENSIONS = {
#     ".py", ".js", ".jsx", ".ts", ".tsx",
#     ".java", ".cpp", ".c", ".h", ".cs",
#     ".go", ".rs", ".rb", ".php", ".swift",
#     ".html", ".css", ".xml", ".sh",
# }

# TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yml", ".yaml"}

# LANGUAGE_MAP = {
#     ".py": "python", ".js": "javascript", ".jsx": "javascript",
#     ".ts": "typescript", ".tsx": "typescript", ".java": "java",
#     ".cpp": "cpp", ".c": "c", ".h": "c", ".cs": "c_sharp",
#     ".go": "go", ".rs": "rust", ".rb": "ruby",
#     ".html": "html", ".css": "css", ".sh": "bash",
# }


# class RepositoryChunker:
#     def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
#         self.chunk_size = chunk_size
#         self.chunk_overlap = chunk_overlap
#         self.text_splitter = SentenceSplitter(
#             chunk_size=chunk_size,
#             chunk_overlap=chunk_overlap,
#         )

#     def chunk_documents(self, documents: List[Document]) -> List[BaseNode]:
#         code_by_lang = defaultdict(list)
#         text_docs = []

#         for doc in documents:
#             ext = Path(doc.metadata.get("file_path", "")).suffix
#             if ext in CODE_EXTENSIONS:
#                 lang = LANGUAGE_MAP.get(ext, "python")
#                 code_by_lang[lang].append(doc)
#             else:
#                 text_docs.append(doc)

#         nodes = []
#         for lang, docs in code_by_lang.items():
#             splitter = CodeSplitter(
#                 language=lang,
#                 chunk_lines=40,
#                 chunk_lines_overlap=5,
#                 max_chars=1500,
#             )
#             nodes += splitter.get_nodes_from_documents(docs)

#         if text_docs:
#             nodes += self.text_splitter.get_nodes_from_documents(text_docs)

#         return nodes

#     def chunk_document(self, document: Document) -> List[BaseNode]:
#         return self.chunk_documents([document])

#     def get_chunk_stats(self, nodes: List[BaseNode]) -> dict:
#         total_tokens = sum(len(node.get_content().split()) for node in nodes)
#         avg_tokens = total_tokens / len(nodes) if nodes else 0
#         return {
#             "total_nodes": len(nodes),
#             "total_tokens": total_tokens,
#             "avg_tokens_per_node": round(avg_tokens, 2),
#             "chunk_size_config": self.chunk_size,
#             "chunk_overlap_config": self.chunk_overlap,
#         }