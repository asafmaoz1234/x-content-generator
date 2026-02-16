"""
Synthesis module for combining scout candidates into coherent angles.
"""
import json
import logging
import openai
import boto3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from source_scout.config import ScoutConfig
from source_scout.normalizer import NewsCandidate

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')


@dataclass
class SourceFact:
    """A fact with source attribution."""
    fact: str
    source_url: str
    source_name: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SourceFact':
        """Create from dictionary."""
        return cls(
            fact=data['fact'],
            source_url=data['source_url'],
            source_name=data['source_name']
        )


@dataclass
class SynthesisResult:
    """Result of synthesizing scout candidates into an angle."""
    angle: str
    hook: str
    key_facts: List[SourceFact] = field(default_factory=list)
    draft_post: str = ""
    source_candidates_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'angle': self.angle,
            'hook': self.hook,
            'key_facts': [fact.to_dict() for fact in self.key_facts],
            'draft_post': self.draft_post,
            'source_candidates_used': self.source_candidates_used
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SynthesisResult':
        """Create from dictionary."""
        return cls(
            angle=data['angle'],
            hook=data['hook'],
            key_facts=[SourceFact.from_dict(fact) for fact in data.get('key_facts', [])],
            draft_post=data.get('draft_post', ''),
            source_candidates_used=data.get('source_candidates_used', [])
        )


def fetch_unused_candidates(config: ScoutConfig, days: int = 7, max_candidates: int = 20) -> List[NewsCandidate]:
    """
    Fetch recent unused candidates from DynamoDB.
    
    Args:
        config: ScoutConfig instance
        days: Number of days to look back (default: 7)
        max_candidates: Maximum number of candidates to return (default: 20)
        
    Returns:
        List of NewsCandidate objects with status='new'
    """
    logger.info('Fetching unused candidates (last %s days)', days)
    
    table = dynamodb.Table(config.news_candidates_table)
    
    # Calculate cutoff date
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    
    try:
        # Query using GSI: topic-published_at-index
        # FilterExpression pushes status filtering to DynamoDB, reducing data transfer
        response = table.query(
            IndexName='topic-published_at-index',
            KeyConditionExpression='topic = :topic AND published_at > :cutoff',
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':topic': config.topic,
                ':cutoff': cutoff_iso,
                ':status': 'new'
            }
        )
        
        items = response.get('Items', [])
        
        # Convert to NewsCandidate objects
        candidates = []
        for item in items:
            try:
                # Convert Decimals to floats
                item = _convert_decimals_to_floats(item)
                
                candidate = NewsCandidate.from_dict(item)
                candidates.append(candidate)
                
                # Respect max limit
                if len(candidates) >= max_candidates:
                    break
                    
            except Exception as e:
                logger.warning(
                    'Failed to parse candidate from DynamoDB: %s',
                    str(e),
                    extra={'extra_data': {'error': str(e)}}
                )
                continue
        
        # Sort by quality score descending
        candidates.sort(key=lambda c: c.quality_score, reverse=True)
        
        logger.info(
            'Found %s unused candidates',
            len(candidates),
            extra={'extra_data': {'count': len(candidates)}}
        )
        
        return candidates
        
    except Exception as e:
        logger.error(
            'Error fetching unused candidates: %s',
            str(e),
            extra={'extra_data': {'error': str(e)}}
        )
        return []


def _convert_decimals_to_floats(obj: Any) -> Any:
    """
    Convert Decimals to floats when reading from DynamoDB.
    Recursively handles nested structures.
    """
    from decimal import Decimal
    
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_floats(item) for item in obj]
    return obj


def synthesize_angle(candidates: List[NewsCandidate], config: ScoutConfig) -> Optional[SynthesisResult]:
    """
    Synthesize scout candidates into a coherent angle using OpenAI.
    
    Args:
        candidates: List of NewsCandidate objects
        config: ScoutConfig instance
        
    Returns:
        SynthesisResult object or None if synthesis fails
    """
    if not candidates:
        logger.warning('No candidates provided for synthesis')
        return None
    
    logger.info('Synthesizing angle from %s candidates', len(candidates))
    
    try:
        # Load synthesis prompt template
        with open('prompts/synthesis_prompt.txt', 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # Format candidates for prompt
        candidates_text = []
        for i, candidate in enumerate(candidates, 1):
            candidates_text.append(
                f"{i}. [{candidate.source_name}] {candidate.title}\n"
                f"   URL: {candidate.canonical_url}\n"
                f"   Description: {candidate.description or 'N/A'}\n"
                f"   Quality Score: {candidate.quality_score:.2f}"
            )
        
        candidates_str = "\n\n".join(candidates_text)
        
        # Format prompt
        prompt = prompt_template.format(
            topic=config.topic,
            candidates=candidates_str,
            num_candidates=len(candidates)
        )
        
        # Call OpenAI
        openai.api_key = config.openai_api_key
        
        response = openai.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        # Parse JSON response
        content = response.choices[0].message.content.strip()
        logger.info('Received synthesis response from OpenAI')
        
        # Parse and validate JSON
        synthesis_data = json.loads(content)
        
        # Validate required fields
        required_fields = ['angle', 'hook', 'key_facts', 'draft_post', 'source_urls']
        for required_field in required_fields:
            if required_field not in synthesis_data:
                raise ValueError(f'Missing required field: {required_field}')
        
        # Convert to SynthesisResult
        key_facts = []
        for fact_data in synthesis_data.get('key_facts', []):
            key_facts.append(SourceFact(
                fact=fact_data['fact'],
                source_url=fact_data['source_url'],
                source_name=fact_data.get('source_name', 'Unknown')
            ))
        
        result = SynthesisResult(
            angle=synthesis_data['angle'],
            hook=synthesis_data['hook'],
            key_facts=key_facts,
            draft_post=synthesis_data['draft_post'],
            source_candidates_used=synthesis_data['source_urls']
        )
        
        logger.info(
            'Successfully synthesized angle',
            extra={'extra_data': {
                'angle': result.angle[:100],
                'num_facts': len(result.key_facts),
                'num_sources': len(result.source_candidates_used)
            }}
        )
        return result
        
    except FileNotFoundError:
        logger.error('Synthesis prompt template not found: prompts/synthesis_prompt.txt')
        return None
    except json.JSONDecodeError as e:
        logger.error('Failed to parse synthesis JSON response: %s', str(e))
        return None
    except Exception as e:
        logger.error(
            'Error during synthesis: %s',
            str(e),
            extra={'extra_data': {'error': str(e)}},
            exc_info=True
        )
        return None


def validate_grounding(result: SynthesisResult, candidates: List[NewsCandidate]) -> bool:
    """
    Validate that synthesis result is grounded in provided candidates.
    
    Args:
        result: SynthesisResult to validate
        candidates: List of NewsCandidate objects that were provided
        
    Returns:
        True if all sources are valid, False if grounding violations detected
    """
    logger.info('Validating synthesis grounding')
    
    # Build set of valid canonical URLs
    valid_urls = {candidate.canonical_url for candidate in candidates}
    
    violations = []
    
    # Check key facts
    for i, fact in enumerate(result.key_facts):
        if fact.source_url not in valid_urls:
            violations.append(f"Fact {i+1} cites invalid URL: {fact.source_url}")
    
    # Check source candidates used
    for url in result.source_candidates_used:
        if url not in valid_urls:
            violations.append(f"Source candidate not in provided set: {url}")
    
    if violations:
        logger.warning(
            'Grounding violations detected: %s',
            '; '.join(violations),
            extra={'extra_data': {'violations': violations}}
        )
        return False
    
    logger.info('Synthesis grounding validated successfully')
    return True
