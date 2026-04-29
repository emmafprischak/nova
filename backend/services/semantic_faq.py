"""
FR-15: Semantic FAQ Search
Uses sentence embeddings and cosine similarity for intelligent FAQ matching
"""
import numpy as np
from typing import Optional, Tuple
import pickle
import os
from backend.services.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Will be initialized lazily on first use
_model = None
_faq_embeddings = None
_faq_keys = None

EMBEDDINGS_CACHE_PATH = "/opt/nova/nova-voice-agent/backend/data/faq_embeddings.pkl"
SIMILARITY_THRESHOLD = 0.5  # Minimum cosine similarity to consider a match

def _get_model():
    """Lazy load the sentence transformer model"""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Use a lightweight, multilingual model that works well for short texts
            _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("Loaded sentence transformer model for semantic FAQ search")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            # Fall back to keyword matching
            return None
    return _model


def _generate_faq_embeddings(faq_data: dict) -> Tuple[np.ndarray, list]:
    """
    Generate embeddings for all FAQ questions and their keywords

    Args:
        faq_data: Dict of FAQ content with keywords

    Returns:
        Tuple of (embeddings array, faq_keys list)
    """
    model = _get_model()
    if model is None:
        return None, None

    faq_texts = []
    faq_keys = []

    for faq_key, faq_content in faq_data.items():
        # Combine all keywords and responses to create a rich representation
        keywords = " ".join(faq_content.get("keywords", []))
        english_text = faq_content.get("english", "")
        spanish_text = faq_content.get("spanish", "")

        # Create a combined text that captures the FAQ's meaning
        combined_text = f"{keywords} {english_text} {spanish_text}"
        faq_texts.append(combined_text)
        faq_keys.append(faq_key)

    # Generate embeddings
    embeddings = model.encode(faq_texts, convert_to_numpy=True, show_progress_bar=False)

    logger.info(f"Generated embeddings for {len(faq_keys)} FAQ entries")
    return embeddings, faq_keys


def initialize_faq_embeddings(faq_data: dict, force_regenerate: bool = False):
    """
    Initialize or load cached FAQ embeddings

    Args:
        faq_data: Dict of FAQ content
        force_regenerate: If True, regenerate embeddings even if cache exists
    """
    global _faq_embeddings, _faq_keys

    # Try to load from cache first
    if not force_regenerate and os.path.exists(EMBEDDINGS_CACHE_PATH):
        try:
            with open(EMBEDDINGS_CACHE_PATH, 'rb') as f:
                cache_data = pickle.load(f)
                _faq_embeddings = cache_data['embeddings']
                _faq_keys = cache_data['faq_keys']
                logger.info(f"Loaded cached FAQ embeddings for {len(_faq_keys)} entries")
                return
        except Exception as e:
            logger.warning(f"Failed to load cached embeddings: {e}. Regenerating...")

    # Generate new embeddings
    _faq_embeddings, _faq_keys = _generate_faq_embeddings(faq_data)

    if _faq_embeddings is not None:
        # Save to cache
        try:
            os.makedirs(os.path.dirname(EMBEDDINGS_CACHE_PATH), exist_ok=True)
            with open(EMBEDDINGS_CACHE_PATH, 'wb') as f:
                pickle.dump({
                    'embeddings': _faq_embeddings,
                    'faq_keys': _faq_keys
                }, f)
            logger.info("Saved FAQ embeddings to cache")
        except Exception as e:
            logger.warning(f"Failed to cache embeddings: {e}")


def semantic_faq_search(user_message: str, language: str = 'english') -> Optional[str]:
    """
    Search for the most relevant FAQ using semantic similarity

    Args:
        user_message: User's question or message
        language: User's language (english/spanish)

    Returns:
        FAQ key if a good match is found, None otherwise
    """
    global _faq_embeddings, _faq_keys

    if not user_message or not user_message.strip():
        return None

    # Ensure embeddings are initialized
    if _faq_embeddings is None or _faq_keys is None:
        from faq_data import FAQ_DATA
        initialize_faq_embeddings(FAQ_DATA)

    # If still None (model failed to load), return None
    if _faq_embeddings is None:
        logger.warning("FAQ embeddings not available, falling back to keyword search")
        return None

    model = _get_model()
    if model is None:
        return None

    try:
        # Generate embedding for user message
        user_embedding = model.encode([user_message], convert_to_numpy=True, show_progress_bar=False)[0]

        # Calculate cosine similarities
        similarities = np.dot(_faq_embeddings, user_embedding) / (
            np.linalg.norm(_faq_embeddings, axis=1) * np.linalg.norm(user_embedding)
        )

        # Find best match
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]

        logger.debug(
            f"Semantic FAQ search: best match '{_faq_keys[best_idx]}' "
            f"with similarity {best_score:.3f}"
        )

        # Only return match if similarity is above threshold
        if best_score >= SIMILARITY_THRESHOLD:
            logger.info(
                f"Semantic FAQ match found",
                faq_key=_faq_keys[best_idx],
                similarity_score=float(best_score),
                user_message=user_message[:50]
            )
            return _faq_keys[best_idx]
        else:
            logger.debug(
                f"No semantic FAQ match (best score {best_score:.3f} below threshold {SIMILARITY_THRESHOLD})"
            )
            return None

    except Exception as e:
        logger.error(f"Error in semantic FAQ search: {e}")
        return None


def hybrid_faq_search(user_message: str, language: str = 'english') -> Optional[str]:
    """
    Hybrid approach: Try semantic search first, fall back to keyword matching

    Args:
        user_message: User's question
        language: User's language

    Returns:
        FAQ key if match found
    """
    # Try semantic search first
    semantic_result = semantic_faq_search(user_message, language)
    if semantic_result:
        return semantic_result

    # Fall back to keyword matching (original implementation)
    from faq_data import FAQ_DATA

    if not user_message:
        return None

    user_message_lower = user_message.lower()

    for faq_key, faq_content in FAQ_DATA.items():
        for keyword in faq_content.get("keywords", []):
            if keyword.lower() in user_message_lower:
                logger.info(
                    f"Keyword FAQ match found",
                    faq_key=faq_key,
                    matched_keyword=keyword
                )
                return faq_key

    return None
