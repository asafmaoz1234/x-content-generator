"""
Deduplication logic: URL canonicalization and semantic similarity filtering.
"""
import logging
import openai
from typing import List, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)
# Tracking parameters to strip from URLs
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'ref', 'source', 'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid',
    '_ga', '_gl', 'campaign_id', 'ad_id'
}


def canonicalize_url(url: str) -> str:
    """
    Canonicalize URL by normalizing and removing tracking parameters.
    
    Args:
        url: Original URL string
        
    Returns:
        Canonicalized URL string
    """
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Normalize scheme to https
        scheme = 'https'
        
        # Lowercase domain and remove www prefix
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        # Remove tracking parameters from query string
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            # Filter out tracking params
            clean_params = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
            # Rebuild query string (sorted for consistency)
            query = urlencode(sorted(clean_params.items()), doseq=True) if clean_params else ''
        else:
            query = ''
        
        # Remove fragment
        fragment = ''
        
        # Remove trailing slash from path
        path = parsed.path.rstrip('/')
        if not path:
            path = '/'
        
        # Reconstruct URL
        canonical = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        
        return canonical
        
    except Exception as e:
        logger.warning('Failed to canonicalize URL: %s', url, extra={'extra_data': {'error': str(e)}})
        # Return original URL if canonicalization fails
        return url


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    Pure Python implementation (no numpy).
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    
    try:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        
        similarity = dot / (norm_a * norm_b)
        # Clamp to [0, 1] range (floating point precision issues)
        return max(0.0, min(1.0, similarity))
        
    except Exception as e:
        logger.warning('Error calculating cosine similarity: %s', str(e))
        return 0.0


def generate_embeddings(texts: List[str], config) -> List[List[float]]:
    """
    Generate OpenAI embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
        config: ScoutConfig with OpenAI credentials
        
    Returns:
        List of embedding vectors
        
    Raises:
        Exception: If embedding generation fails
    """
    if not texts:
        return []
    
    logger.info('Generating embeddings for %s texts', len(texts))
    
    try:
        # Set OpenAI API key
        openai.api_key = config.openai_api_key
        
        # Generate embeddings using text-embedding-3-small model
        response = openai.embeddings.create(
            model='text-embedding-3-small',
            input=texts
        )
        
        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]
        
        logger.info(
            'Successfully generated embeddings',
            extra={'extra_data': {
                'count': len(embeddings),
                'dimension': len(embeddings[0]) if embeddings else 0
            }}
        )
        
        return embeddings
        
    except Exception as e:
        logger.error('Failed to generate embeddings: %s', str(e))
        raise


def deduplicate(candidates: List, config) -> List:
    """
    Deduplicate candidates using URL canonicalization and semantic similarity.
    
    Steps:
    1. Canonicalize URLs
    2. Check DynamoDB for existing URLs
    3. Generate embeddings for new candidates
    4. Filter by semantic similarity against recent candidates
    
    Args:
        candidates: List of NewsCandidate objects
        config: ScoutConfig instance
        
    Returns:
        List of deduplicated NewsCandidate objects
    """
    from source_scout.store import get_existing_urls, get_recent_embeddings
    
    if not candidates:
        return []
    
    logger.info('Starting deduplication for %s candidates', len(candidates))
    
    # Step 1: Canonicalize URLs
    logger.info('Canonicalizing URLs')
    for candidate in candidates:
        candidate.canonical_url = canonicalize_url(candidate.original_url)
    
    # Step 2: Check for existing URLs in DynamoDB
    logger.info('Checking for existing URLs in DynamoDB')
    canonical_urls = [c.canonical_url for c in candidates]
    existing_urls = get_existing_urls(canonical_urls, config.topic, config.news_candidates_table)
    
    logger.info(
        'Found %s existing URLs',
        len(existing_urls),
        extra={'extra_data': {'existing_count': len(existing_urls)}}
    )
    
    # Filter out existing URLs
    new_candidates = [c for c in candidates if c.canonical_url not in existing_urls]
    
    if not new_candidates:
        logger.info('All candidates already exist in database')
        return []
    
    logger.info('%s new candidates after URL deduplication', len(new_candidates))
    
    # Step 3: Generate embeddings for new candidates
    logger.info('Generating embeddings for new candidates')
    
    # Combine title and description for embedding
    texts_to_embed = []
    for candidate in new_candidates:
        text = candidate.title
        if candidate.description:
            text = f"{candidate.title}. {candidate.description}"
        texts_to_embed.append(text)
    
    try:
        embeddings = generate_embeddings(texts_to_embed, config)
        
        # Assign embeddings to candidates
        for candidate, embedding in zip(new_candidates, embeddings):
            candidate.embedding = embedding
            
    except Exception as e:
        logger.error('Failed to generate embeddings, skipping semantic deduplication: %s', str(e))
        # Return candidates without semantic filtering if embedding fails
        return new_candidates
    
    # Step 4: Semantic similarity filtering
    logger.info('Fetching recent embeddings for semantic similarity check')
    
    try:
        recent_candidates = get_recent_embeddings(
            config.topic,
            days=7,
            table_name=config.news_candidates_table
        )
        
        if not recent_candidates:
            logger.info('No recent candidates found for similarity comparison')
            return new_candidates
        
        logger.info('Comparing against %s recent candidates', len(recent_candidates))
        
        # Filter out semantically similar candidates
        unique_candidates = []
        
        for candidate in new_candidates:
            is_duplicate = False
            max_similarity = 0.0
            
            for recent in recent_candidates:
                if not recent.embedding:
                    continue
                
                similarity = cosine_similarity(candidate.embedding, recent.embedding)
                max_similarity = max(max_similarity, similarity)
                
                if similarity >= config.similarity_threshold:
                    logger.info(
                        'Filtering out semantically similar candidate',
                        extra={'extra_data': {
                            'title': candidate.title,
                            'similar_to': recent.title,
                            'similarity': similarity
                        }}
                    )
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_candidates.append(candidate)
            else:
                logger.debug(
                    'Candidate filtered as duplicate (max_similarity: %.3f)',
                    max_similarity,
                    extra={'extra_data': {'title': candidate.title}}
                )
        
        logger.info(
            'Deduplication complete: %s unique candidates (filtered %s)',
            len(unique_candidates),
            len(new_candidates) - len(unique_candidates),
            extra={'extra_data': {
                'unique_count': len(unique_candidates),
                'filtered_count': len(new_candidates) - len(unique_candidates)
            }}
        )
        
        return unique_candidates
        
    except Exception as e:
        logger.error('Error during semantic similarity filtering: %s', str(e))
        # Return candidates without semantic filtering if it fails
        return new_candidates
