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
        logger.info("Initializing RAGAgent")
        self.config = {
            "chroma_store_dir": CHROMA_STORE_DIR,
            "embedding_model": EMBEDDING_MODEL,
            "top_k": RAG_TOP_K,
            "similarity_threshold": RAG_SIMILARITY_THRESHOLD,
        }
        self._retriever = None
        self._model_pool = None
        logger.info(f"RAGAgent initialized with config: {self.config}")

    def get_retriever(self) -> VectorIndexRetriever:
        if self._retriever is None:
            logger.info("Creating retriever - getting index")
            index = rag_ingestion.get_index()
            if index is None:
                logger.warning("Index is None, retriever not available")
                return None

            self._retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=self.config["top_k"],
            )
            logger.info("Retriever created successfully")
        return self._retriever

    def generate_response(self, query: str, context: str) -> str:
        try:
            logger.info(f"Generating response for query: {query[:50]}...")
            model = ModelPool()

            prompt = f"""基于以下参考信息回答用户问题。如果参考信息与问题相关，请根据参考信息回答；如果参考信息不相关，请说明无法回答。
                    参考信息：
                    {context}
                    用户问题：{query}
                    回答："""
            result = model.invoke([HumanMessage(content=prompt)])
            logger.info(f"Response generated successfully: {result.content[:50]}...")
            return result.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return context

    def retrieve(self, query: str) -> Tuple[bool, str]:
        try:
            logger.info(f"Starting retrieval for query: {query}")
            retriever = self.get_retriever()
            if retriever is None:
                logger.warning("Retriever is None, returning empty")
                return False, ""

            nodes = retriever.retrieve(query)
            logger.info(f"Retrieved {len(nodes)} nodes")
            if not nodes:
                logger.warning("No nodes retrieved")
                return False, ""

            threshold = self.config.get("similarity_threshold", 0.5)
            relevant_nodes = [n for n in nodes if n.score >= threshold]
            logger.info(
                f"Found {len(relevant_nodes)} relevant nodes (threshold: {threshold})"
            )

            if not relevant_nodes:
                logger.warning("No relevant nodes found")
                return False, ""

            context_parts = []
            for node in relevant_nodes:
                context_parts.append(node.node.get_content())

            context = "\n\n".join(context_parts)
            logger.info(f"Context assembled, length: {len(context)}")

            response = self.generate_response(query, context)

            logger.info(f"Retrieval successful, response length: {len(response)}")
            return True, response

        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return False, ""

    def is_answerable(self, query: str) -> bool:
        logger.info(f"Checking if query is answerable: {query}")
        success, _ = self.retrieve(query)
        logger.info(f"Query answerable: {success}")
        return success


rag_agent = RAGAgent()
