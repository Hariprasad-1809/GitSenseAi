import logging
import hashlib
from typing import List, Dict
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings

logger = logging.getLogger(__name__)


class CodeEmbedder:
    """
    Lightweight, low-memory API-based embedding generator using external OpenAI / OpenRouter API.
    Default Model: text-embedding-3-small (1536 dimensions).
    Includes memory caching, dynamic batching, and tenacity retries with exponential backoff.
    RAM usage is < 5MB (Zero PyTorch, CUDA, or local ML model weight dependencies).
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL or "text-embedding-3-small"
        self._cache: Dict[str, List[float]] = {}
        
        # Determine API key and Base URL
        api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
        base_url = settings.EMBEDDING_BASE_URL.strip() if settings.EMBEDDING_BASE_URL else ""
        
        if api_key:
            logger.info("Initializing API CodeEmbedder with OPENAI_API_KEY (model='%s').", self.model_name)
            if not base_url:
                base_url = "https://api.openai.com/v1"
        else:
            # Fallback to OPENROUTER_API_KEY if OPENAI_API_KEY is empty
            api_key = settings.OPENROUTER_API_KEY.strip()
            base_url = settings.OPENROUTER_BASE_URL.strip() or "https://openrouter.ai/api/v1"
            logger.info("Initializing API CodeEmbedder with OPENROUTER_API_KEY (model='%s', base_url='%s').", self.model_name, base_url)

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _call_embedding_api(self, batch_texts: List[str]) -> List[List[float]]:
        """
        Executes OpenAI / OpenRouter embedding API call with retries and backoff.
        """
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=batch_texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error("Embedding API call failed for batch of %d items: %s", len(batch_texts), e)
            raise

    def embed_chunks(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generates embeddings for list of code/text chunks using batching and hash caching.
        """
        if not texts:
            return []

        results: List[List[float]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Check cache
        for idx, text in enumerate(texts):
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            if text_hash in self._cache:
                results[idx] = self._cache[text_hash]
            else:
                uncached_indices.append(idx)
                cleaned = text.strip() if text.strip() else "empty_code_chunk"
                uncached_texts.append(cleaned[:8000])  # Cap long chunks to 8k chars

        # Batch call external embedding API
        if uncached_texts:
            for i in range(0, len(uncached_texts), batch_size):
                batch_slice = uncached_texts[i : i + batch_size]
                indices_slice = uncached_indices[i : i + batch_size]
                
                batch_embeddings = self._call_embedding_api(batch_slice)
                
                for orig_idx, orig_text, emb in zip(indices_slice, [texts[j] for j in indices_slice], batch_embeddings):
                    results[orig_idx] = emb
                    text_hash = hashlib.md5(orig_text.encode("utf-8")).hexdigest()
                    if len(self._cache) < 50000:
                        self._cache[text_hash] = emb

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
        """
        res = self.embed_chunks([query])
        return res[0] if res else []


# Global embedder instance (lazy loaded when first accessed)
_embedder_instance = None


def get_embedder() -> CodeEmbedder:
    """
    Returns the singleton instance of the CodeEmbedder.
    """
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = CodeEmbedder()
    return _embedder_instance
