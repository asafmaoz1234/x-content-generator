"""
DynamoDB storage operations for news candidates.
"""
import logging
import boto3
from datetime import datetime, timedelta
from typing import List, Set, Dict, Any
from decimal import Decimal

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize DynamoDB resource outside handler (per Lambda best practices)
dynamodb = boto3.resource('dynamodb')


def _convert_floats_to_decimals(obj: Any) -> Any:
    """
    Convert floats to Decimals for DynamoDB storage.
    Recursively handles nested structures.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimals(item) for item in obj]
    return obj


def _convert_decimals_to_floats(obj: Any) -> Any:
    """
    Convert Decimals to floats when reading from DynamoDB.
    Recursively handles nested structures.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_floats(item) for item in obj]
    return obj


def save_candidates(candidates: List, table_name: str) -> None:
    """
    Save news candidates to DynamoDB.
    
    Args:
        candidates: List of NewsCandidate objects
        table_name: DynamoDB table name
    """
    if not candidates:
        logger.info('No candidates to save')
        return
    
    logger.info('Saving %s candidates to DynamoDB', len(candidates))
    
    table = dynamodb.Table(table_name)
    
    # Calculate TTL (30 days from published_at)
    saved_count = 0
    
    for candidate in candidates:
        try:
            # Convert candidate to dict
            item = candidate.to_dict()
            
            # Add TTL (30 days from now)
            ttl = datetime.utcnow() + timedelta(days=30)
            item['expires_at'] = int(ttl.timestamp())
            
            # Convert floats to Decimals for DynamoDB
            item = _convert_floats_to_decimals(item)
            
            # Put item
            table.put_item(Item=item)
            saved_count += 1
            
        except Exception as e:
            logger.error(
                'Failed to save candidate: %s',
                str(e),
                extra={'extra_data': {
                    'error': str(e),
                    'candidate': candidate.title
                }}
            )
            continue
    
    logger.info(
        'Successfully saved %s/%s candidates',
        saved_count,
        len(candidates),
        extra={'extra_data': {
            'saved_count': saved_count,
            'total_count': len(candidates)
        }}
    )


def get_existing_urls(urls: List[str], topic: str, table_name: str) -> Set[str]:
    """
    Check which URLs already exist in DynamoDB.
    
    Args:
        urls: List of canonical URLs to check
        topic: Topic string
        table_name: DynamoDB table name
        
    Returns:
        Set of URLs that already exist
    """
    if not urls:
        return set()
    
    logger.info('Checking %s URLs against DynamoDB', len(urls))
    
    table = dynamodb.Table(table_name)
    existing = set()
    
    # DynamoDB batch_get_item has a limit of 100 items
    # Process in chunks of 100
    for i in range(0, len(urls), 100):
        chunk = urls[i:i+100]
        
        try:
            # Build keys for batch get
            keys = [{'canonical_url': url, 'topic': topic} for url in chunk]
            
            response = dynamodb.batch_get_item(
                RequestItems={
                    table_name: {
                        'Keys': keys
                    }
                }
            )
            
            # Extract existing URLs from response
            items = response.get('Responses', {}).get(table_name, [])
            for item in items:
                existing.add(item['canonical_url'])
            
        except Exception as e:
            logger.error(
                'Error checking existing URLs: %s',
                str(e),
                extra={'extra_data': {'error': str(e), 'chunk_size': len(chunk)}}
            )
            # Continue with other chunks even if one fails
            continue
    
    logger.info(
        'Found %s existing URLs out of %s checked',
        len(existing),
        len(urls),
        extra={'extra_data': {'existing_count': len(existing), 'checked_count': len(urls)}}
    )
    
    return existing


def get_recent_embeddings(topic: str, days: int, table_name: str) -> List:
    """
    Fetch recent candidates with embeddings for semantic similarity comparison.
    
    Args:
        topic: Topic string
        days: Number of days to look back
        table_name: DynamoDB table name
        
    Returns:
        List of NewsCandidate objects with embeddings
    """
    from source_scout.normalizer import NewsCandidate
    
    logger.info('Fetching recent candidates with embeddings (last %s days)', days)
    
    table = dynamodb.Table(table_name)
    
    # Calculate cutoff date
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    
    try:
        # Query using GSI: topic-published_at-index
        response = table.query(
            IndexName='topic-published_at-index',
            KeyConditionExpression='topic = :topic AND published_at > :cutoff',
            ExpressionAttributeValues={
                ':topic': topic,
                ':cutoff': cutoff_iso
            }
        )
        
        items = response.get('Items', [])
        
        # Convert to NewsCandidate objects
        candidates = []
        for item in items:
            try:
                # Convert Decimals to floats
                item = _convert_decimals_to_floats(item)
                
                # Only include if it has embeddings
                if item.get('embedding'):
                    candidate = NewsCandidate.from_dict(item)
                    candidates.append(candidate)
            except Exception as e:
                logger.warning(
                    'Failed to parse candidate from DynamoDB: %s',
                    str(e),
                    extra={'extra_data': {'error': str(e)}}
                )
                continue
        
        logger.info(
            'Found %s recent candidates with embeddings',
            len(candidates),
            extra={'extra_data': {'count': len(candidates)}}
        )
        
        return candidates
        
    except Exception as e:
        logger.error(
            'Error fetching recent embeddings: %s',
            str(e),
            extra={'extra_data': {'error': str(e)}}
        )
        return []


def mark_candidate_used(canonical_url: str, topic: str, table_name: str) -> None:
    """
    Mark a candidate as used (e.g., after posting to X).
    
    Args:
        canonical_url: Canonical URL of the candidate
        topic: Topic string
        table_name: DynamoDB table name
    """
    logger.info('Marking candidate as used: %s', canonical_url)
    
    table = dynamodb.Table(table_name)
    
    try:
        table.update_item(
            Key={
                'canonical_url': canonical_url,
                'topic': topic
            },
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'used'
            }
        )
        
        logger.info('Successfully marked candidate as used')
        
    except Exception as e:
        logger.error(
            'Failed to mark candidate as used: %s',
            str(e),
            extra={'extra_data': {'error': str(e), 'url': canonical_url}}
        )
        raise
