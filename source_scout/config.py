"""
Configuration loading and validation for Source Scout Agent.
"""
import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

@dataclass
class ScoutConfig:
    """Configuration for the Source Scout Agent."""
    
    # Required
    newsapi_api_key: str
    news_candidates_table: str
    topic: str
    
    # OpenAI (reused from existing setup)
    openai_api_key: str
    openai_model: str
    
    # Optional with defaults
    time_window_hours: int = 24
    min_relevance_score: float = 0.6
    min_quality_score: float = 0.5
    similarity_threshold: float = 0.92
    max_candidates: int = 20
    
    @classmethod
    def from_env(cls) -> 'ScoutConfig':
        """
        Load configuration from environment variables.
        
        Raises:
            KeyError: If required environment variables are missing
            ValueError: If configuration values are invalid
        """
        logger.info('Loading Source Scout configuration from environment')
        
        # Required variables
        newsapi_api_key = os.environ['NEWSAPI_API_KEY']
        news_candidates_table = os.environ['NEWS_CANDIDATES_TABLE']
        topic = os.environ['CONTENT_TOPIC']
        openai_api_key = os.environ['OPENAI_API_KEY']
        openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4')
        
        # Optional with defaults
        time_window_hours = int(os.environ.get('NEWS_TIME_WINDOW_HOURS', '24'))
        min_relevance_score = float(os.environ.get('NEWS_MIN_RELEVANCE_SCORE', '0.6'))
        min_quality_score = float(os.environ.get('NEWS_MIN_QUALITY_SCORE', '0.5'))
        similarity_threshold = float(os.environ.get('NEWS_SIMILARITY_THRESHOLD', '0.92'))
        max_candidates = int(os.environ.get('NEWS_MAX_CANDIDATES', '20'))
        
        # Validation
        if time_window_hours < 1 or time_window_hours > 168:  # 1 hour to 1 week
            raise ValueError(f'NEWS_TIME_WINDOW_HOURS must be between 1 and 168, got {time_window_hours}')
        
        if not (0.0 <= min_relevance_score <= 1.0):
            raise ValueError(f'NEWS_MIN_RELEVANCE_SCORE must be between 0.0 and 1.0, got {min_relevance_score}')
        
        if not (0.0 <= min_quality_score <= 1.0):
            raise ValueError(f'NEWS_MIN_QUALITY_SCORE must be between 0.0 and 1.0, got {min_quality_score}')
        
        if not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError(f'NEWS_SIMILARITY_THRESHOLD must be between 0.0 and 1.0, got {similarity_threshold}')
        
        if max_candidates < 1 or max_candidates > 100:
            raise ValueError(f'NEWS_MAX_CANDIDATES must be between 1 and 100, got {max_candidates}')
        
        config = cls(
            newsapi_api_key=newsapi_api_key,
            news_candidates_table=news_candidates_table,
            topic=topic,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            time_window_hours=time_window_hours,
            min_relevance_score=min_relevance_score,
            min_quality_score=min_quality_score,
            similarity_threshold=similarity_threshold,
            max_candidates=max_candidates
        )
        
        logger.info(
            'Configuration loaded successfully',
            extra={'extra_data': {
                'topic': topic,
                'time_window_hours': time_window_hours,
                'max_candidates': max_candidates
            }}
        )
        
        return config
