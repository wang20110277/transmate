import asyncio
import logging
from app.llm.rag import rag_ingestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def build_rag_index(force_rebuild: bool = False):
    """构建RAG索引"""
    logger.info("Starting RAG index build...")
    try:
        index = rag_ingestion.build_index(force_rebuild=force_rebuild)
        if index:
            logger.info("RAG index built successfully")
            return True
        else:
            logger.warning("RAG index build returned None")
            return False
    except Exception as e:
        logger.error(f"Failed to build RAG index: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(build_rag_index(force_rebuild=True))
    if success:
        print("RAG index built successfully!")
    else:
        print("Failed to build RAG index")
