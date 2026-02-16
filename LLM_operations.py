import os
import logging
import openai
from typing import Optional
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def generate_content_with_retry(prompt: str, max_retries: int = 3) -> str:
    """
    Generate content using OpenAI API with retry logic.
    
    Args:
        prompt: The prompt to send to OpenAI
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        Generated content as string
        
    Raises:
        Exception: If all retry attempts fail
    """
    # Initialize OpenAI client
    openai.api_key = os.environ['OPENAI_API_KEY']
    model = os.environ.get('OPENAI_MODEL', 'gpt-4')
    max_tokens = os.environ.get('CONTENT_MAX_CHARACTERS', 1500)
    
    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                'Calling OpenAI API (attempt %s/%s)',
                attempt, max_retries,
                extra={'extra_data': {'model': model, 'attempt': attempt}}
            )
            
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                max_tokens=max_tokens*2,  # X character limit
                temperature=0.7
            )
            
            # Extract generated content
            content = response.choices[0].message.content.strip()
            logger.info(
                'Content generated successfully',
                extra={'extra_data': {'content': content, 'attempt': attempt}}
            )
            
            return content
            
        except Exception as e:
            last_exception = e
            logger.warning(
                'OpenAI API call failed (attempt %s/%s): %s',
                attempt, max_retries, str(e),
                extra={'extra_data': {'error': str(e), 'attempt': attempt}}
            )
            
            # If this wasn't the last attempt, wait before retrying
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
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
