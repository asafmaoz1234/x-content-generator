import os
from typing import Dict
import tweepy
from logger_util import logger
from prompt_builder import build_prompt


def process_reply(reply_event: Dict) -> Dict:
    """
    Process a single reply event and generate a response.
    
    Args:
        reply_event: Dictionary containing reply data including:
            - reply_id: ID of the reply tweet
            - reply_text: Content of the reply
            - author_id: ID of the reply author
            
    Returns:
        Dictionary with response details
    """
    logger.info('Processing reply event',
                extra={'extra_data': {
                    'reply_id': reply_event['reply_id']
                }})

    try:
        # Generate response using prompt builder
        prompt = build_prompt({
            'topic': 'reply',
            'keywords': ['response', 'engagement'],
            'tone': 'conversational',
            'content': reply_event['reply_text'],
            'min_char_count': '50'
        }, 'reply', os.environ['REPLY_TEMPLATE'])

        # Here you would integrate with your OpenAI call to generate the response
        # response_text = await generate_ai_response(prompt)
        response_text = "Thank you for your reply! [Generated response will go here]"

        # Initialize X client
        client = tweepy.Client(
            consumer_key=os.environ['X_CONSUMER_KEY'],
            consumer_secret=os.environ['X_CONSUMER_SECRET'],
            access_token=os.environ['X_ACCESS_TOKEN'],
            access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET']
        )

        # Post the response
        response = client.create_tweet(
            text=response_text,
            in_reply_to_tweet_id=reply_event['reply_id']
        )

        logger.info('Successfully responded to reply',
                    extra={'extra_data': {
                        'reply_id': reply_event['reply_id'],
                        'response_id': response.data['id']
                    }})

        return {
            'status': 'success',
            'reply_id': reply_event['reply_id'],
            'response_id': response.data['id'],
            'response_text': response_text
        }

    except Exception as e:
        logger.error('Error processing reply',
                     extra={'extra_data': {
                         'reply_id': reply_event.get('reply_id'),
                         'error': str(e)
                     }},
                     exc_info=True)
        raise