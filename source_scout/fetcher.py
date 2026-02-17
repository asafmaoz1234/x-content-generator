"""
NewsAPI client with retry logic and time-window filtering.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from newsapi import NewsApiClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def fetch_news(config) -> List[Dict[str, Any]]:
    """
    Fetch news articles from NewsAPI with retry logic.
    
    Args:
        config: ScoutConfig instance with API key, topic, time window, etc.
    
    Returns:
        List of raw article dictionaries from NewsAPI
        
    Raises:
        Exception: If all retry attempts fail
    """
    max_retries = 3
    last_exception = None
    
    # Calculate time window
    to_date = datetime.utcnow()
    from_date = to_date - timedelta(hours=config.time_window_hours)
    
    logger.info(
        'Fetching news from NewsAPI',
        extra={'extra_data': {
            'topic': config.topic,
            'from_date': from_date.isoformat(),
            'to_date': to_date.isoformat(),
            'max_results': config.max_candidates
        }}
    )
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                'Calling NewsAPI (attempt %s/%s)',
                attempt, max_retries,
                extra={'extra_data': {'attempt': attempt}}
            )
            
            # Initialize NewsAPI client
            newsapi = NewsApiClient(api_key=config.newsapi_api_key)
            
            # Fetch articles using everything endpoint
            response = newsapi.get_everything(
                q=config.topic,
                language='en',
                sort_by='publishedAt',
                from_param=from_date.strftime('%Y-%m-%d'),
                to=to_date.strftime('%Y-%m-%d'),
                page_size=config.max_candidates,
                page=1
            )
            
            # Extract articles from response
            if response.get('status') == 'ok':
                articles = response.get('articles', [])
                logger.info(
                    'Successfully fetched articles from NewsAPI',
                    extra={'extra_data': {
                        'article_count': len(articles),
                        'attempt': attempt
                    }}
                )
                return articles
            else:
                error_msg = response.get('message', 'Unknown error')
                logger.warning(
                    'NewsAPI returned non-ok status: %s',
                    error_msg,
                    extra={'extra_data': {'status': response.get('status'), 'attempt': attempt}}
                )
                raise Exception(f'NewsAPI error: {error_msg}')
                
        except Exception as e:
            last_exception = e
            logger.warning(
                'Unexpected error in NewsAPI call (attempt %s/%s): %s',
                attempt, max_retries, str(e),
                extra={'extra_data': {'error': str(e), 'attempt': attempt}}
            )
            
            # If this wasn't the last attempt, wait before retrying
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info('Waiting %s seconds before retry...', wait_time)
                time.sleep(wait_time)
            else:
                logger.error(
                    'All %s attempts failed',
                    max_retries,
                    extra={'extra_data': {'error': str(e)}}
                )
    
    # If we've exhausted all retries, raise the last exception
    raise last_exception
