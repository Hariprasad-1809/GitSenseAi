import logging
import hashlib
from typing import List, Dict
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class CodeEmbedder:
    """
    Local high-performance embedding generator using SentenceTransformers BAAI/bge-small-en-v1.5 model (384-dimensional).
    Includes dynamic batching, text hash caching to avoid re-embedding identical code blocks, and optimized encoding parameters.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        logger.info(f"Loading local SentenceTransformer model '{model_name}'...")
        try:
            self.model = SentenceTransformer(model_name)
            self._cache: Dict[str, List[float]] = {}
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed_chunks(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """
        Generates embeddings for list of code/text chunks using batching and hash caching.
        Each chunk is prefixed with 'Represent this code for retrieval:'.
        """
        if not texts:
            return []

        results: List[List[float]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_prefixed: List[str] = []

        # Check cache
        for idx, text in enumerate(texts):
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            if text_hash in self._cache:
                results[idx] = self._cache[text_hash]
            else:
                uncached_indices.append(idx)
                uncached_prefixed.append(f"Represent this code for retrieval: {text}")

        # Batch encode uncached texts
        if uncached_prefixed:
            embeddings = self.model.encode(
                uncached_prefixed,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            for idx, text, emb in zip(uncached_indices, [texts[i] for i in uncached_indices], embeddings):
                emb_list = emb.tolist()
                results[idx] = emb_list
                text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
                # Bound cache size to prevent memory leaks (max 50,000 cached chunks)
                if len(self._cache) < 50000:
                    self._cache[text_hash] = emb_list

        return results

    def embed_chunk(self, text: str) -> List[float]:
        """
        Generates embedding for a single chunk.
        """
        res = self.embed_chunks([text])
        return res[0] if res else []

    def embed_query(self, query: str) -> List[float]:
        """
        Generates embedding for search query.
        Queries are prefixed with 'Represent this sentence for searching relevant passages:'.
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
