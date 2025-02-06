import json
import os
from typing import Dict, Any, List
import openai
from datetime import datetime

import tweepy

import reply_x_util
from prompt_builder import build_prompt
from x_poster import post_to_x
from logger_util import logger


def load_prompt_template(template_type: str = 'post') -> str:
    """
    Load the prompt template from file.

    Args:
        template_type: Either 'post' or 'reply' to load appropriate template
    """
    try:
        filename = 'prompts/social_media_prompt.txt' if template_type == 'post' else 'prompts/reply_prompt.txt'
        with open(filename, 'r') as file:
            return file.read()
    except Exception as e:
        logger.error(f'Error loading {template_type} template: {str(e)}')
        # Fallback prompts
        if template_type == 'reply':
            return "You are a social media manager.\nCreate a friendly reply to: {content}\nTone: {tone}"
        return "You are a social media content creator.\nCreate a post about {topic}.\nTone: {tone}"


def process_reply_thread(client: tweepy.Client, message: Dict[Any, Any], thread: Dict, model: str, prompt_template: str) -> Dict:
    """
    Process a single reply thread by generating and posting a response.
    """
    try:
        # Get the last reply in the thread
        last_reply = thread[-1]

        # Build prompt with thread context
        message['reply_text'] = last_reply['text']
        message['thread_context'] = [reply['text'] for reply in thread]
        logger.info('Building prompt with thread context',
                    extra={'extra_data': {'reply_text': message['reply_text'],
                                          'thread_context': message['thread_context']}})
        prompt = build_prompt(message, 'sqs-reply', prompt_template)
        logger.info('Prompt reply:', extra={'extra_data': {'prompt': prompt}})

        # Generate response using OpenAI
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt}
            ],
            max_tokens=280,
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()

        # Post the reply
        post_id = post_to_x(client, content, last_reply['id'])

        return {
            'reply_id': last_reply['id'],
            'response_id': post_id,
            'content': content
        }

    except Exception as e:
        logger.error('Error processing reply thread',
                     extra={'extra_data': {
                         'reply_id': last_reply.get('id'),
                         'error': str(e)
                     }})
        raise


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
        model = os.environ.get('OPENAI_MODEL', 'gpt-4')

        # Initialize X API client
        x_client = tweepy.Client(
            consumer_key=os.environ['X_CONSUMER_KEY'],
            consumer_secret=os.environ['X_CONSUMER_SECRET'],
            access_token=os.environ['X_ACCESS_TOKEN'],
            access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET']
        )

        # Process based on event type
        if 'Records' in event:  # SQS event
            message = json.loads(event['Records'][0]['body'])
            message_id = event['Records'][0].get('messageId')
            logger.info('Processing SQS message',
                        extra={'extra_data': {'message_id': message_id}})

            if 'post_id' in message:  # Handle reply event
                logger.info('Processing SQS REPLY message',
                            extra={'extra_data': {'message': message}})
                post_id = message.get('post_id')
                original_author_id = message.get('original_author_id')

                # Get all reply threads needing response
                reply_threads = reply_x_util.fetch_replies_to_post(post_id, original_author_id)

                if not reply_threads:
                    logger.info('No replies requiring response',
                                extra={'extra_data': {'post_id': post_id}})
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'message': 'No replies requiring response',
                            'timestamp': datetime.utcnow().isoformat()
                        })
                    }

                # Load reply prompt template
                prompt_template = load_prompt_template('reply')
                errors = None
                # Process each thread
                processed_replies = []
                for thread in reply_threads:
                    try:
                        result = process_reply_thread(x_client, message, thread, model, prompt_template)
                        processed_replies.append(result)
                        logger.info('Successfully processed reply thread',
                                    extra={'extra_data': result})
                    except Exception as e:
                        logger.error('Error processing reply thread',
                                     extra={'extra_data': {
                                         'error': str(e),
                                         'thread': thread
                                     }})
                        errors = errors + e
                        continue  # Continue with next thread even if one fails

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Successfully processed reply threads',
                        'processed_replies': processed_replies,
                        'errors': str(errors),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                }

            else:
                # Handle regular post
                event_type = 'sqs'
        else:
            # Handle scheduled post
            message = event
            event_type = 'schedule'
            logger.info('Processing EventBridge event',
                        extra={'extra_data': {'event_id': event.get('id')}})

        # Handle regular post logic
        prompt_template = load_prompt_template('post')
        prompt = build_prompt(message, event_type, prompt_template)

        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt}
            ],
            max_tokens=280,
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()
        post_id = post_to_x(x_client, content)

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
