import logging
import asyncio
from openai import OpenAI
import openai
from app.config import settings

logger = logging.getLogger(__name__)

# Custom application exceptions for LLM operations
class LLMError(Exception):
    """Base exception for LLM-related issues."""
    pass

class LLMAuthenticationError(LLMError):
    """Raised when the API key is invalid."""
    pass

class LLMRateLimitError(LLMError):
    """Raised when the rate limit (429) is hit."""
    pass

class LLMTimeoutError(LLMError):
    """Raised when the request times out."""
    pass

class LLMNetworkError(LLMError):
    """Raised when there are connection/network issues."""
    pass

class LLMInvalidModelError(LLMError):
    """Raised when the requested model is invalid or not found."""
    pass


# Initialize the OpenRouter client using OpenAI Python SDK
client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.OPENROUTER_BASE_URL,
)

# In-memory ACTIVE_MODEL initialized from settings.LLM_MODEL
ACTIVE_MODEL = settings.LLM_MODEL


async def call_gemini_async(system_prompt: str, user_prompt: str) -> str:
    """
    Calls the OpenRouter API asynchronously using the OpenAI client.
    Maintains the original name and interface to keep the rest of the RAG pipeline unchanged.
    Implements runtime fallback logic for model-specific errors (404, 410).
    """
    global ACTIVE_MODEL

    # Compile the sequence of models to try
    models_to_try = [ACTIVE_MODEL]
    for fallback in settings.LLM_FALLBACK_MODELS:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_error = None

    for model in models_to_try:
        ACTIVE_MODEL = model
        logger.info(
            "\n=================================================="
            f"\nACTIVE_MODEL = {ACTIVE_MODEL}"
            f"\nsettings.LLM_MODEL = {settings.LLM_MODEL}"
            "\n=================================================="
        )
        try:
            # Log the COMPLETE prompt sent to OpenRouter
            logger.info(
                "\n================ PROMPT BEGIN ================\n"
                f"System Prompt:\n{system_prompt}\n\n"
                f"User Prompt:\n{user_prompt}\n"
                "================ PROMPT END ==================\n"
            )

            # Run blocking OpenAI SDK call in thread pool to prevent blocking the async event loop
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=ACTIVE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            
            text = response.choices[0].message.content
            if not text:
                raise LLMError("Empty response received from OpenRouter API.")

            # Log the RAW OpenRouter response
            logger.info(
                "\n=============== RAW LLM RESPONSE ===============\n"
                f"{text}\n"
                "===============================================\n"
            )

            # If fallback succeeded, update ACTIVE_MODEL and log switch info
            if model != ACTIVE_MODEL:
                logger.warning("Switched active model to %s", model)
                ACTIVE_MODEL = model

            return text

        except openai.APIStatusError as e:
            # Switch models only on model-specific errors (404: Not Found, 410: Gone/Deprecated)
            if e.status_code in (404, 410):
                logger.warning(
                    f"Model '{model}' failed with status {e.status_code}: {e}. Trying next model."
                )
                last_error = e
                continue
            else:
                # Do not retry/switch on transient errors (like 429, 500, 502, 503, timeout, etc.)
                logger.error("OpenRouter API Status Error (HTTP %s): %s", e.status_code, e)
                if e.status_code == 400 and "model" in str(e).lower():
                    raise LLMInvalidModelError(f"Invalid model specified: {e}")
                elif e.status_code == 401:
                    raise LLMAuthenticationError(f"Invalid API key: {e}")
                elif e.status_code == 429:
                    raise LLMRateLimitError(f"Rate limit exceeded: {e}")
                raise LLMError(f"OpenRouter API returned error status {e.status_code}: {e}")

        except openai.AuthenticationError as e:
            logger.error(f"OpenRouter Authentication Error: {e}")
            raise LLMAuthenticationError(f"Invalid API key or unauthorized access: {e}")
        except openai.RateLimitError as e:
            logger.error(f"OpenRouter Rate Limit Error: {e}")
            raise LLMRateLimitError(f"Rate limit exceeded or quota exhausted: {e}")
        except openai.APITimeoutError as e:
            logger.error(f"OpenRouter Timeout Error: {e}")
            raise LLMTimeoutError(f"OpenRouter API request timed out: {e}")
        except openai.APIConnectionError as e:
            logger.error(f"OpenRouter Network/Connection Error: {e}")
            raise LLMNetworkError(f"Network error communicating with OpenRouter: {e}")
        except openai.BadRequestError as e:
            logger.error(f"OpenRouter Bad Request: {e}")
            if "model" in str(e).lower():
                raise LLMInvalidModelError(f"Invalid model specified: {e}")
            raise LLMError(f"Bad request sent to OpenRouter: {e}")
        except openai.OpenAIError as e:
            logger.error(f"OpenRouter SDK Error: {e}")
            raise LLMError(f"OpenRouter SDK encountered an error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error calling OpenRouter API: {e}")
            raise LLMError(f"Unexpected error: {e}")

    if last_error:
        raise LLMError(
            f"All attempted models {models_to_try} are unavailable on OpenRouter (Last Error HTTP {last_error.status_code}: {last_error})."
        )
    raise LLMError(f"All attempted models {models_to_try} failed to respond.")
