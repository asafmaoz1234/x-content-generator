import os
import tweepy
from typing import Optional
from logger_util import logger


def post_to_x(content: str) -> str:
    """
    Posts content to X using the Tweepy library.
    """
    logger.info('Initializing X API client')

    try:
        # Initialize X API client
        client = tweepy.Client(
            consumer_key=os.environ['X_CONSUMER_KEY'],
            consumer_secret=os.environ['X_CONSUMER_SECRET'],
            access_token=os.environ['X_ACCESS_TOKEN'],
            access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET']
        )

        logger.info('Validating API credentials')
        try:
            # Test API credentials by getting account info
            client.get_me()
            logger.info('API credentials validated successfully')
        except tweepy.errors.Unauthorized:
            logger.error('Invalid API credentials')
            raise Exception('Invalid X API credentials. Please check your keys and tokens.')
        except tweepy.errors.Forbidden as e:
            logger.error(f'API permission error: {str(e)}')
            raise Exception('X API permission error. Please check your app permissions in the Twitter Developer Portal.')

        logger.info('Posting content to X',
                    extra={'extra_data': {'content_length': len(content)}})

        # Post to X
        try:
            response = client.create_tweet(text=content)

            post_id = response.data['id']
            logger.info('Successfully posted to X',
                        extra={'extra_data': {'post_id': post_id}})

            return post_id

        except tweepy.errors.Forbidden as e:
            logger.error(f'Error posting tweet: {str(e)}',
                         extra={'extra_data': {
                             'error_code': getattr(e, 'api_codes', []),
                             'error_messages': getattr(e, 'api_messages', [])
                         }})
            raise Exception(f'Failed to post tweet. Error: {str(e)}')

    except Exception as e:
        logger.error('Error in X posting process',
                     extra={'extra_data': {'error': str(e)}},
                     exc_info=True)
        raise
