import logging
import os
from pathlib import Path
from typing import List, Optional
import shutil

logger = logging.getLogger(__name__)

import chromadb
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core.readers import SimpleDirectoryReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.core.config import (
    KNOWLEDGE_DIR,
    CHROMA_STORE_DIR,
    EMBEDDING_MODEL,
    RAG_TOP_K,
    RAG_SIMILARITY_THRESHOLD,
)


class DocumentIngestion:
    def __init__(self):
        self.config = {
            "knowledge_dir": KNOWLEDGE_DIR,
            "chroma_store_dir": CHROMA_STORE_DIR,
            "embedding_model": EMBEDDING_MODEL,
            "top_k": RAG_TOP_K,
            "similarity_threshold": RAG_SIMILARITY_THRESHOLD,
        }
        self._embedding_model = None
        self._index = None
        self._chroma_client = None

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            model_name = self.config["embedding_model"]

            cache_dir = os.environ.get("HF_HOME", str(Path(__file__).parent / "models"))

            local_model_path = (
                Path(cache_dir) / f"models--{model_name.replace('/', '--')}"
            )
            local_files_only = local_model_path.exists()

            logger.info(f"Loading embedding model: {model_name}")
            logger.info(f"Cache dir: {cache_dir}, local_files_only: {local_files_only}")

            self._embedding_model = HuggingFaceEmbedding(
                model_name=model_name,
                device="cpu",
                cache_folder=cache_dir,
                local_files_only=local_files_only,
            )

            logger.info("Embedding model loaded successfully")
        return self._embedding_model

    def load_documents(self) -> List[Document]:
        knowledge_dir = self.config["knowledge_dir"]
        if not os.path.exists(knowledge_dir):
            logger.warning(f"Knowledge directory does not exist: {knowledge_dir}")
            return []

        reader = SimpleDirectoryReader(
            input_dir=knowledge_dir,
            recursive=True,
            exclude_hidden=True,
        )
        documents = reader.load_data()
        logger.info(f"Loaded {len(documents)} documents from {knowledge_dir}")
        return documents

    def build_index(self, force_rebuild: bool = False):
        store_dir = self.config["chroma_store_dir"]

        if force_rebuild:
            try:
                shutil.rmtree(store_dir)
                logger.info(f"Deleted existing store directory: {store_dir}")
            except Exception as e:
                logger.warning(f"Failed to delete store directory: {e}")

        os.makedirs(store_dir, exist_ok=True)

        chroma_client = chromadb.PersistentClient(path=store_dir)
        collection_name = "knowledge_base"

        chroma_collection = chroma_client.get_or_create_collection(name=collection_name)

        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        documents = self.load_documents()
        if not documents:
            logger.warning("No documents to index")
            return None

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            embed_model=self.embedding_model,
            show_progress=True,
        )

        logger.info(f"Index built successfully with {len(documents)} documents")
        return self._index

    def get_index(self) -> Optional[VectorStoreIndex]:
        import shutil

        if self._index is not None:
            return self._index

        store_dir = self.config["chroma_store_dir"]

        try:
            chroma_client = chromadb.PersistentClient(path=store_dir)
            collection_name = "knowledge_base"

            chroma_collection = chroma_client.get_or_create_collection(
                name=collection_name
            )
            if chroma_collection.count() == 0:
                logger.warning("Collection is empty, building index...")
                return self.build_index(force_rebuild=True)

            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            self._index = VectorStoreIndex.from_vector_store(
                vector_store,
                embed_model=self.embedding_model,
            )
            return self._index
        except Exception as e:
            logger.error(f"Failed to load index: {e}, rebuilding...")
            try:
                shutil.rmtree(store_dir)
            except:
                pass
            try:
                return self.build_index(force_rebuild=True)
            except Exception as rebuild_error:
                logger.error(f"Failed to rebuild index: {rebuild_error}")
                return None


rag_ingestion = DocumentIngestion()
