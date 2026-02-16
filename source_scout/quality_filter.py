"""
Quality filtering: source reputation, title clarity, and domain relevance.
"""
import logging
import json
import re
import openai
from typing import List, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Source reputation scores (0.0-1.0)
SOURCE_REPUTATION = {
    # Tier 1: Premium tech/news sources
    'techcrunch.com': 0.95,
    'reuters.com': 0.95,
    'bloomberg.com': 0.95,
    'theverge.com': 0.90,
    'wired.com': 0.90,
    'arstechnica.com': 0.90,
    'technologyreview.com': 0.90,
    'theguardian.com': 0.90,
    'nytimes.com': 0.90,
    'wsj.com': 0.90,
    
    # Tier 2: Reputable tech blogs
    'venturebeat.com': 0.85,
    'zdnet.com': 0.85,
    'cnet.com': 0.85,
    'engadget.com': 0.80,
    'gizmodo.com': 0.80,
    'mashable.com': 0.80,
    'techradar.com': 0.75,
    'digitaltrends.com': 0.75,
    
    # Tier 3: Industry-specific
    'axios.com': 0.85,
    'businessinsider.com': 0.80,
    'forbes.com': 0.75,
    'fastcompany.com': 0.75,
    'fortune.com': 0.75,
    
    # Tier 4: Developer/technical sources
    'github.blog': 0.85,
    'stackoverflow.blog': 0.80,
    'hackernoon.com': 0.70,
    
    # Tier 5: Medium quality (user-generated)
    'medium.com': 0.50,
    'dev.to': 0.55,
    'substack.com': 0.50,
    
    # Add more as needed...
}

# Default reputation for unknown sources
DEFAULT_REPUTATION = 0.40

# Clickbait patterns (case-insensitive)
CLICKBAIT_PATTERNS = [
    r'\byou won\'?t believe\b',
    r'\bshocking\b',
    r'\bamaz(ing|ed)\b.*\bhappens?\b',
    r'\bthis one (weird )?trick\b',
    r'\bnumber \d+ will\b',
    r'\bwhat happens next\b',
    r'\bthe reason why\b',
    r'\bdoctors hate (him|her|this)\b',
    r'\b\d+ reasons? why\b',
    r'\bmind[\s-]?blown\b',
]


def get_source_reputation(domain: str) -> float:
    """
    Get reputation score for a source domain.
    
    Args:
        domain: Domain name (e.g., 'techcrunch.com')
        
    Returns:
        Reputation score (0.0-1.0)
    """
    return SOURCE_REPUTATION.get(domain.lower(), DEFAULT_REPUTATION)


def check_title_clarity(title: str) -> bool:
    """
    Check if title meets clarity standards.
    
    Args:
        title: Article title
        
    Returns:
        True if title passes clarity checks, False otherwise
    """
    if not title:
        return False
    
    # Check length
    if len(title) < 20 or len(title) > 300:
        logger.debug('Title fails length check: %s chars', len(title))
        return False
    
    # Check for all-caps (allow up to 30% caps)
    alpha_chars = [c for c in title if c.isalpha()]
    if alpha_chars:
        caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if caps_ratio > 0.7:
            logger.debug('Title has too many capitals: %.0f%%', caps_ratio * 100)
            return False
    
    # Check for excessive punctuation
    if '!!!' in title or '???' in title or '?!' in title * 2:
        logger.debug('Title has excessive punctuation')
        return False
    
    # Check for clickbait patterns
    title_lower = title.lower()
    for pattern in CLICKBAIT_PATTERNS:
        if re.search(pattern, title_lower):
            logger.debug('Title matches clickbait pattern: %s', pattern)
            return False
    
    return True


def classify_relevance_batch(candidates: List, topic: str, config) -> List[float]:
    """
    Use OpenAI to classify domain relevance for a batch of candidates.
    
    Args:
        candidates: List of NewsCandidate objects
        topic: Topic string for relevance check
        config: ScoutConfig with OpenAI credentials
        
    Returns:
        List of relevance scores (0.0-1.0) for each candidate
    """
    if not candidates:
        return []
    
    logger.info('Classifying relevance for %s candidates', len(candidates))
    
    # Build prompt with all candidates
    articles_text = []
    for i, candidate in enumerate(candidates):
        articles_text.append(
            f"{i+1}. Title: {candidate.title}\n"
            f"   Description: {candidate.description or 'N/A'}\n"
            f"   Source: {candidate.source_name}"
        )
    
    articles_str = "\n\n".join(articles_text)
    
    system_prompt = f"""You are an expert content curator evaluating news articles for relevance to a specific topic.

Topic: {topic}

For each article below, assign a relevance score from 0.0 to 1.0:
- 1.0 = Highly relevant, directly about {topic}
- 0.7-0.9 = Relevant, discusses {topic} in meaningful way
- 0.4-0.6 = Somewhat relevant, mentions {topic} tangentially
- 0.0-0.3 = Not relevant, unrelated to {topic}

Articles:

{articles_str}

Respond with ONLY a JSON array of scores in order, nothing else. Example: [0.9, 0.5, 0.2, ...]"""
    
    try:
        # Set OpenAI API key
        openai.api_key = config.openai_api_key
        
        # Call OpenAI chat completion
        response = openai.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Extract and parse JSON response
        content = response.choices[0].message.content.strip()
        
        # Handle potential markdown code blocks
        if content.startswith('```'):
            # Extract content between code fences
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1]) if len(lines) > 2 else content
            content = content.replace('```json', '').replace('```', '').strip()
        
        scores = json.loads(content)
        
        if not isinstance(scores, list) or len(scores) != len(candidates):
            logger.error('Invalid response format from OpenAI: expected %s scores, got %s', len(candidates), len(scores))
            # Return default scores
            return [0.5] * len(candidates)
        
        # Validate and clamp scores
        validated_scores = []
        for score in scores:
            try:
                score = float(score)
                score = max(0.0, min(1.0, score))
                validated_scores.append(score)
            except (ValueError, TypeError):
                logger.warning('Invalid score value: %s, using 0.5', score)
                validated_scores.append(0.5)
        
        logger.info(
            'Successfully classified relevance',
            extra={'extra_data': {
                'count': len(validated_scores),
                'avg_score': sum(validated_scores) / len(validated_scores) if validated_scores else 0
            }}
        )
        
        return validated_scores
        
    except json.JSONDecodeError as e:
        logger.error('Failed to parse OpenAI response as JSON: %s', str(e))
        return [0.5] * len(candidates)
        
    except Exception as e:
        logger.error('Error calling OpenAI for relevance classification: %s', str(e))
        return [0.5] * len(candidates)


def filter_quality(candidates: List, config) -> List:
    """
    Filter candidates by quality and relevance.
    
    Steps:
    1. Check title clarity
    2. Get source reputation
    3. Classify domain relevance via OpenAI
    4. Calculate composite quality score
    5. Filter by minimum quality threshold
    
    Args:
        candidates: List of NewsCandidate objects
        config: ScoutConfig instance
        
    Returns:
        List of filtered NewsCandidate objects that pass quality checks
    """
    if not candidates:
        return []
    
    logger.info('Starting quality filtering for %s candidates', len(candidates))
    
    # Step 1 & 2: Title clarity and source reputation
    passed_basic = []
    
    for candidate in candidates:
        # Check language
        if candidate.language.lower() != 'en':
            logger.debug('Filtering non-English article: %s', candidate.title)
            continue
        
        # Check title clarity
        if not check_title_clarity(candidate.title):
            logger.debug('Filtering article with poor title: %s', candidate.title)
            continue
        
        passed_basic.append(candidate)
    
    if not passed_basic:
        logger.info('All candidates filtered out by basic quality checks')
        return []
    
    logger.info('%s candidates passed basic quality checks', len(passed_basic))
    
    # Step 3: Classify relevance using OpenAI
    relevance_scores = classify_relevance_batch(passed_basic, config.topic, config)
    
    # Assign scores to candidates
    for candidate, relevance_score in zip(passed_basic, relevance_scores):
        candidate.relevance_score = relevance_score
    
    # Step 4: Calculate composite quality scores
    qualified_candidates = []
    
    for candidate in passed_basic:
        # Get source reputation
        reputation = get_source_reputation(candidate.source_domain)
        
        # Title quality: binary (1.0 if passed checks, 0.0 otherwise)
        title_quality = 1.0  # Already passed checks above
        
        # Composite score: 40% reputation + 30% title quality + 30% relevance
        quality_score = (0.4 * reputation) + (0.3 * title_quality) + (0.3 * candidate.relevance_score)
        
        candidate.quality_score = quality_score
        
        logger.debug(
            'Quality score for "%s": %.3f (rep: %.2f, title: %.2f, rel: %.2f)',
            candidate.title[:50],
            quality_score,
            reputation,
            title_quality,
            candidate.relevance_score,
            extra={'extra_data': {
                'title': candidate.title,
                'quality_score': quality_score,
                'reputation': reputation,
                'relevance_score': candidate.relevance_score
            }}
        )
        
        # Filter by minimum quality threshold
        if quality_score >= config.min_quality_score:
            qualified_candidates.append(candidate)
        else:
            logger.debug('Filtering candidate below quality threshold: %s (score: %.3f)', candidate.title, quality_score)
    
    logger.info(
        'Quality filtering complete: %s qualified candidates (filtered %s)',
        len(qualified_candidates),
        len(candidates) - len(qualified_candidates),
        extra={'extra_data': {
            'qualified_count': len(qualified_candidates),
            'filtered_count': len(candidates) - len(qualified_candidates)
        }}
    )
    
    return qualified_candidates
