import json
import os
from typing import Dict, Any
import openai
from datetime import datetime

import tweepy

from prompt_builder import build_prompt
from x_poster import post_to_x
from logger_util import logger


def load_prompt_template() -> str:
    """Load the prompt template from file."""
    try:
        with open('prompts/social_media_prompt.txt', 'r') as file:
            return file.read()
    except Exception as e:
        logger.error(f'Error loading prompt template: {str(e)}')
        # Fallback to basic prompt if file can't be loaded
        return "You are a social media content creator.\nCreate a post about {topic}.\nTone: {tone}"


def lambda_handler(event: Dict[Any, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler that processes SQS messages or EventBridge events,
    generates content using OpenAI, and posts to X.
    """
    request_id = context.aws_request_id if context else 'local'
    logger.info('Starting lambda execution', extra={'extra_data': {'request_id': request_id}})

    try:
        # Initialize OpenAI client
        openai.api_key = os.environ['OPENAI_API_KEY']
        model = os.environ.get('OPENAI_MODEL', 'gpt-4')  # Default to gpt-4 if not specified

        # Load prompt template
        prompt_template = load_prompt_template()

        # Determine event source and extract relevant data
        if 'Records' in event:  # SQS event
            message = json.loads(event['Records'][0]['body'])
            event_type = 'sqs'
            logger.info('Processing SQS message',
                        extra={'extra_data': {'message_id': event['Records'][0].get('messageId')}})
        else:  # EventBridge scheduled event
            message = event
            event_type = 'schedule'
            logger.info('Processing EventBridge event',
                        extra={'extra_data': {'event_id': event.get('id')}})

        # Build prompt based on event data
        logger.info('Building prompt', extra={'extra_data': {'event_type': event_type}})
        prompt = build_prompt(message, event_type, prompt_template)

        # Generate content using OpenAI
        logger.info('Calling OpenAI API', extra={'extra_data': {'model': model}})
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt}
            ],
            max_tokens=280,  # X character limit
            temperature=0.7
        )

        # Extract generated content
        content = response.choices[0].message.content.strip()
        logger.info('Content generated successfully',
                    extra={'extra_data': {'content_length': len(content)}})

        # Initialize X API client
        x_client = tweepy.Client(
            consumer_key=os.environ['X_CONSUMER_KEY'],
            consumer_secret=os.environ['X_CONSUMER_SECRET'],
            access_token=os.environ['X_ACCESS_TOKEN'],
            access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET']
        )

        # Post to X
        logger.info('Posting content to X')
        post_id = post_to_x(x_client, content, reply_id, author_id)
        logger.info('Successfully posted to X',
                    extra={'extra_data': {'post_id': post_id}})

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully posted to X',
                'content': content,
                'post_id': post_id,
                'timestamp': datetime.utcnow().isoformat()
            })
        }

    except Exception as e:
        logger.error('Error in lambda execution',
                     extra={'extra_data': {'error': str(e)}},
                     exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }
