import logging
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class CodeEmbedder:
    """
    Local embedding generator using the SentenceTransformers BAAI/bge-small-en-v1.5 model (384-dimensional).
    It runs inference locally and prefixes chunks/queries according to the retrieval instructions.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        logger.info(f"Loading local SentenceTransformer model '{model_name}'...")
        try:
            self.model = SentenceTransformer(model_name)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed_chunks(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for list of code/text chunks.
        Each chunk is prefixed with 'Represent this code for retrieval:'.
        """
        if not texts:
            return []
        
        prefixed_texts = [f"Represent this code for retrieval: {t}" for t in texts]
        embeddings = self.model.encode(
            prefixed_texts, 
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return [emb.tolist() for emb in embeddings]

    def embed_chunk(self, text: str) -> List[float]:
        """
        Generates embedding for a single chunk.
        """
        res = self.embed_chunks([text])
        return res[0] if res else []

    def embed_query(self, query: str) -> List[float]:
        """
        Generates embedding for search query.
        Queries are prefixed with 'Represent this sentence for searching relevant passages:' for BGE search performance.
        """
        prefixed_query = f"Represent this sentence for searching relevant passages: {query}"
        embedding = self.model.encode(
            prefixed_query, 
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embedding.tolist()


# Global embedder instance (lazy loaded when first accessed to prevent importing slowdowns)
_embedder_instance = None


def get_embedder() -> CodeEmbedder:
    """
    Returns the singleton instance of the CodeEmbedder.
    """
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = CodeEmbedder()
    return _embedder_instance
