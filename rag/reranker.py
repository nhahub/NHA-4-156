from typing import List, Optional
from sentence_transformers import CrossEncoder
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from pydantic import Field

_reranker_instance = None


def get_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 5):
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = RepoReranker(model_name=model_name, top_k=top_k)
    return _reranker_instance


class RepoReranker(BaseNodePostprocessor):
    top_k: int = Field(default=5)
    _model: CrossEncoder = PrivateAttr()

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 5):
        super().__init__(top_k=top_k)
        self._model = CrossEncoder(model_name)


    def _postprocess_nodes(
        self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        if not nodes or not query_bundle:
            return nodes

        pairs = [(query_bundle.query_str, n.node.get_content()) for n in nodes]
        scores = self._model.predict(pairs)

        for n, s in zip(nodes, scores):
            n.score = float(s)

        nodes.sort(key=lambda n: n.score, reverse=True)
        return nodes[:self.top_k]