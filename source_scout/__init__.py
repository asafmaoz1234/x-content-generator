"""
Source Scout Agent package for fetching and normalizing news content.
"""
from source_scout.config import ScoutConfig
from source_scout.fetcher import fetch_news
from source_scout.normalizer import NewsCandidate, normalize_articles
from source_scout.dedup import deduplicate
from source_scout.quality_filter import filter_quality
from source_scout.store import save_candidates, get_existing_urls, get_recent_embeddings, mark_candidate_used

__all__ = [
    'ScoutConfig',
    'fetch_news',
    'NewsCandidate',
    'normalize_articles',
    'deduplicate',
    'filter_quality',
    'save_candidates',
    'get_existing_urls',
    'get_recent_embeddings',
    'mark_candidate_used',
]
