"""
Schema normalization for news articles.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

@dataclass
class NewsCandidate:
    """Normalized news article candidate."""
    
    canonical_url: str
    original_url: str
    title: str
    description: str
    source_name: str
    source_domain: str
    published_at: str  # ISO 8601
    fetched_at: str  # ISO 8601
    language: str
    topic: str
    relevance_score: float = 0.0
    quality_score: float = 0.0
    embedding: List[float] = field(default_factory=list)
    status: str = "new"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        return {
            'canonical_url': self.canonical_url,
            'original_url': self.original_url,
            'title': self.title,
            'description': self.description or '',
            'source_name': self.source_name,
            'source_domain': self.source_domain,
            'published_at': self.published_at,
            'fetched_at': self.fetched_at,
            'language': self.language,
            'topic': self.topic,
            'relevance_score': self.relevance_score,
            'quality_score': self.quality_score,
            'embedding': self.embedding,
            'status': self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewsCandidate':
        """Create from dictionary (e.g., from DynamoDB)."""
        return cls(
            canonical_url=data['canonical_url'],
            original_url=data['original_url'],
            title=data['title'],
            description=data.get('description', ''),
            source_name=data['source_name'],
            source_domain=data['source_domain'],
            published_at=data['published_at'],
            fetched_at=data['fetched_at'],
            language=data['language'],
            topic=data['topic'],
            relevance_score=data.get('relevance_score', 0.0),
            quality_score=data.get('quality_score', 0.0),
            embedding=data.get('embedding', []),
            status=data.get('status', 'new')
        )


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: Full URL string
        
    Returns:
        Domain name (e.g., 'techcrunch.com')
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception as e:
        logger.warning('Failed to extract domain from URL: %s', url, extra={'extra_data': {'error': str(e)}})
        return ''


def normalize_articles(raw_articles: List[Dict[str, Any]], topic: str) -> List[NewsCandidate]:
    """
    Transform raw NewsAPI articles into normalized NewsCandidate objects.
    
    Args:
        raw_articles: List of raw article dicts from NewsAPI
        topic: Topic string for tagging
        
    Returns:
        List of NewsCandidate objects
    """
    logger.info('Normalizing %s raw articles', len(raw_articles))
    
    normalized = []
    fetched_at = datetime.utcnow().isoformat()
    
    for article in raw_articles:
        try:
            # Extract required fields
            url = article.get('url')
            if not url:
                logger.warning('Article missing URL, skipping')
                continue
            
            title = article.get('title', '').strip()
            if not title:
                logger.warning('Article missing title, skipping: %s', url)
                continue
            
            # Extract source info
            source = article.get('source', {})
            source_name = source.get('name', 'Unknown') if isinstance(source, dict) else 'Unknown'
            source_domain = extract_domain(url)
            
            # Get description (may be null)
            description = article.get('description', '') or ''
            description = description.strip()
            
            # Get published date
            published_at = article.get('publishedAt', '')
            if not published_at:
                # Fallback to current time if no publish date
                published_at = datetime.utcnow().isoformat()
            
            # Get language (default to 'en' since we filter for it)
            language = article.get('language', 'en')
            
            # Create candidate (canonical_url will be set by dedup module)
            candidate = NewsCandidate(
                canonical_url=url,  # Will be updated by canonicalization
                original_url=url,
                title=title,
                description=description,
                source_name=source_name,
                source_domain=source_domain,
                published_at=published_at,
                fetched_at=fetched_at,
                language=language,
                topic=topic,
                status='new'
            )
            
            normalized.append(candidate)
            
        except Exception as e:
            logger.warning(
                'Failed to normalize article: %s',
                str(e),
                extra={'extra_data': {'error': str(e), 'article': article}}
            )
            continue
    
    logger.info(
        'Normalized %s articles successfully',
        len(normalized),
        extra={'extra_data': {'count': len(normalized)}}
    )
    
    return normalized
