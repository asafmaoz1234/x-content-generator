"""
Source Scout Agent runner module.
Orchestrates the news fetching, deduplication, and quality filtering pipeline.
"""
import logging
from typing import Dict, Any
from source_scout import (
    ScoutConfig,
    fetch_news,
    normalize_articles,
    deduplicate,
    filter_quality,
    save_candidates
)

logger = logging.getLogger(__name__)

logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def run_scout() -> Dict[str, Any]:
    """
    Run the Source Scout Agent pipeline.
    Fetches news articles, deduplicates, filters for quality,
    and stores qualified candidates in DynamoDB.
    
    Returns:
        Dictionary with status and results information
    """
    logger.info('Starting Source Scout Agent')
    
    try:
        # Load configuration from environment
        config = ScoutConfig.from_env()
        
        # Fetch news from NewsAPI
        raw_articles = fetch_news(config)
        logger.info('Fetched %s raw articles', len(raw_articles))
        
        if not raw_articles:
            logger.info('No articles fetched, exiting')
            return {
                'success': True,
                'message': 'No articles found',
                'candidates_stored': 0
            }
        
        # Normalize articles to NewsCandidate objects
        candidates = normalize_articles(raw_articles, config.topic)
        logger.info('Normalized to %s candidates', len(candidates))
        
        if not candidates:
            logger.info('No valid candidates after normalization')
            return {
                'success': True,
                'message': 'No valid candidates after normalization',
                'candidates_stored': 0
            }
        
        # Deduplicate (URL canonicalization + semantic similarity)
        candidates = deduplicate(candidates, config)
        logger.info('After deduplication: %s candidates', len(candidates))
        
        if not candidates:
            logger.info('All candidates filtered as duplicates')
            return {
                'success': True,
                'message': 'All candidates were duplicates',
                'candidates_stored': 0
            }
        
        # Filter by quality and relevance
        candidates = filter_quality(candidates, config)
        logger.info('After quality filtering: %s candidates', len(candidates))
        
        if not candidates:
            logger.info('All candidates filtered by quality checks')
            return {
                'success': True,
                'message': 'No candidates passed quality checks',
                'candidates_stored': 0
            }
        
        # Save to DynamoDB
        save_candidates(candidates, config.news_candidates_table)
        
        logger.info(
            'Source Scout Agent completed successfully',
            extra={'extra_data': {'candidates_stored': len(candidates)}}
        )
        
        return {
            'success': True,
            'message': 'Successfully stored news candidates',
            'candidates_stored': len(candidates)
        }
        
    except KeyError as e:
        logger.error('Missing required environment variable: %s', str(e), exc_info=True)
        return {
            'success': False,
            'error': f'Missing required environment variable: {str(e)}',
            'candidates_stored': 0
        }
        
    except Exception as e:
        logger.error(
            'Error in scout runner execution',
            extra={'extra_data': {'error': str(e)}},
            exc_info=True
        )
        return {
            'success': False,
            'error': str(e),
            'candidates_stored': 0
        }
