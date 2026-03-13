import logging
from typing import Tuple

from llama_index.core.retrievers import VectorIndexRetriever
from langchain_core.messages import HumanMessage

from app.llm.rag.ingestion import rag_ingestion
from app.core.config import (
    CHROMA_STORE_DIR,
    EMBEDDING_MODEL,
    RAG_TOP_K,
    RAG_SIMILARITY_THRESHOLD,
)
from app.llm.models.qwen_model import ModelPool

logger = logging.getLogger(__name__)


class RAGAgent:
    def __init__(self):
        self.config = {
            "chroma_store_dir": CHROMA_STORE_DIR,
            "embedding_model": EMBEDDING_MODEL,
            "top_k": RAG_TOP_K,
            "similarity_threshold": RAG_SIMILARITY_THRESHOLD,
        }
        self._retriever = None
        self._model_pool = None

    def _get_retriever(self) -> VectorIndexRetriever:
        if self._retriever is None:
            index = rag_ingestion.get_index()
            if index is None:
                logger.warning("RAG index not available")
                return None

            self._retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=self.config["top_k"],
            )
        return self._retriever

    def _get_model_pool(self):
        if self._model_pool is None:
            self._model_pool = ModelPool(size=1)
            self._model_pool.initialize_models()
        return self._model_pool

    def _generate_response(self, query: str, context: str) -> str:
        try:
            model_pool = self._get_model_pool()
            model = model_pool._get_model()

            prompt = f"""基于以下参考信息回答用户问题。如果参考信息与问题相关，请根据参考信息回答；如果参考信息不相关，请说明无法回答。
                    参考信息：
                    {context}
                    用户问题：{query}
                    回答："""
            result = model.invoke([HumanMessage(content=prompt)])
            return result.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return context

    def retrieve(self, query: str) -> Tuple[bool, str]:
        try:
            retriever = self._get_retriever()
            if retriever is None:
                return False, ""

            nodes = retriever.retrieve(query)
            if not nodes:
                return False, ""

            threshold = self.config.get("similarity_threshold", 0.5)
            relevant_nodes = [n for n in nodes if n.score >= threshold]

            if not relevant_nodes:
                logger.info(
                    f"RAG: no nodes above threshold {threshold} for query: {query}"
                )
                return False, ""

            context_parts = []
            for node in relevant_nodes:
                context_parts.append(node.node.get_content())

            context = "\n\n".join(context_parts)

            response = self._generate_response(query, context)

            logger.info(
                f"RAG retrieved {len(relevant_nodes)} relevant sources (threshold: {threshold}) for query: {query}"
            )
            return True, response

        except Exception as e:
            logger.error(f"RAG retrieval error: {e}")
            return False, ""

    def is_answerable(self, query: str) -> bool:
        success, _ = self.retrieve(query)
        return success


rag_agent = RAGAgent()
