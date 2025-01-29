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

        logger.info('Posting content to X',
                    extra={'extra_data': {'content_length': len(content)}})

        # Post to X
        response = client.create_tweet(text=content)

        post_id = response.data['id']
        logger.info('Successfully posted to X',
                    extra={'extra_data': {'post_id': post_id}})

        return post_id

    except Exception as e:
        logger.error('Error posting to X',
                     extra={'extra_data': {'error': str(e)}},
                     exc_info=True)
        raise