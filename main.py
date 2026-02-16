import json
import os
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from prompt_builder import build_prompt
from x_poster import post_to_x
from LLM_operations import generate_content_with_retry
from scout_runner import run_scout
from synthesizer import fetch_unused_candidates, synthesize_angle, validate_grounding, SynthesisResult
from source_scout import ScoutConfig, mark_candidate_used

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def load_prompt_template() -> str:
    """Load the prompt template from file."""
    try:
        with open('prompts/social_media_prompt.txt', 'r') as file:
            return file.read()
    except Exception as e:
        logger.error('Error loading prompt template: %s', str(e))
        # Fallback to basic prompt if file can't be loaded
        return "You are a social media content creator.\nCreate a post about {topic}.\nTone: {tone}"


def lambda_handler(event: Dict[Any, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler that processes EventBridge events.
    
    First runs the Source Scout Agent to fetch and store news candidates,
    synthesizes them into a coherent angle, generates content using OpenAI,
    and posts to X.
    """

    try:
        logger.info('Processing EventBridge event', extra={'extra_data': {'event_id': event.get('id')}})
        
        # Step 1: Run Source Scout Agent to fetch and store news candidates
        logger.info('Running Source Scout Agent')
        scout_result = run_scout()
        
        if not scout_result.get('success'):
            logger.warning(
                'Scout failed but continuing with content generation',
                extra={'extra_data': {'scout_error': scout_result.get('error')}}
            )
        else:
            logger.info(
                'Scout completed: %s candidates stored',
                scout_result.get('candidates_stored', 0)
            )
        
        # Step 2: Synthesize angle from unused candidates
        synthesis_result = None
        try:
            config = ScoutConfig.from_env()
            
            # Fetch unused candidates
            candidates = fetch_unused_candidates(config, days=7, max_candidates=20)
            
            if candidates:
                logger.info('Found %s unused candidates for synthesis', len(candidates))
                
                # Synthesize angle
                synthesis_result = synthesize_angle(candidates, config)
                
                if synthesis_result:
                    # Validate grounding
                    is_grounded = validate_grounding(synthesis_result, candidates)
                    if not is_grounded:
                        logger.warning('Synthesis has grounding violations but continuing')
                    
                    logger.info(
                        'Successfully synthesized angle: %s',
                        synthesis_result.angle[:100],
                        extra={'extra_data': {
                            'angle': synthesis_result.angle[:100],
                            'num_sources': len(synthesis_result.source_candidates_used)
                        }}
                    )
                else:
                    logger.warning('Synthesis failed, falling back to generic prompt')
            else:
                logger.info('No unused candidates available for synthesis, using generic prompt')
                
        except Exception as e:
            logger.warning(
                'Error during synthesis, falling back to generic prompt: %s',
                str(e),
                extra={'extra_data': {'error': str(e)}}
            )
            synthesis_result = None
        
        # Step 3: Load prompt template
        prompt_template = load_prompt_template()

        # Step 4: Build prompt based on event data and synthesis result
        prompt = build_prompt(event, prompt_template, synthesis_result=synthesis_result)

        # Step 5: Generate content using OpenAI with retry logic
        content = generate_content_with_retry(prompt, max_retries=3)

        # Step 6: Post to X
        logger.info('Posting content to X')
        post_id = post_to_x(content)
        logger.info('Successfully posted to X', extra={'extra_data': {'post_id': post_id}})
        
        # Step 7: Mark used candidates
        if synthesis_result and synthesis_result.source_candidates_used:
            logger.info('Marking %s candidates as used', len(synthesis_result.source_candidates_used))
            for url in synthesis_result.source_candidates_used:
                try:
                    mark_candidate_used(url, config.topic, config.news_candidates_table)
                except Exception as e:
                    logger.warning('Failed to mark candidate as used: %s', str(e))

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully posted to X',
                'content': content,
                'post_id': post_id,
                'scout_result': scout_result,
                'synthesis_used': synthesis_result is not None,
                'timestamp': datetime.utcnow().isoformat()
            })
        }

    except Exception as e:
        logger.error('Error in lambda execution', extra={'extra_data': {'error': str(e)}}, exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }


