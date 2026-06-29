from typing import List, Optional, Any
from sentence_transformers import CrossEncoder
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from pydantic import Field


class RepoReranker(BaseNodePostprocessor):
    model: Any = Field(default=None, exclude=True)
    top_k: int = Field(default=5)

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 5):
        super().__init__()
        self.model = CrossEncoder(model_name)
        self.top_k = top_k

    def _postprocess_nodes(
        self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        if not nodes or not query_bundle:
            return nodes

        pairs = [(query_bundle.query_str, n.node.get_content()) for n in nodes]
        scores = self.model.predict(pairs)

        for n, s in zip(nodes, scores):
            n.score = float(s)

        nodes.sort(key=lambda n: n.score, reverse=True)
        return nodes[:self.top_k]