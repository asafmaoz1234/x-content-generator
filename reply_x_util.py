import tweepy
from typing import Optional
from logger_util import logger


def fetch_post_text(client: tweepy.Client, post_id: str) -> Optional[str]:
    """
    Fetches the text content of a post by its ID.

    Args:
        client: An initialized tweepy.Client instance
        post_id: The ID of the post to fetch

    Returns:
        The text content of the post or None if not found/error

    Raises:
        Exception: If there's an error fetching the tweet
    """
    try:
        logger.info('Fetching post content',
                    extra={'extra_data': {'post_id': post_id}})

        # Get tweet with full text expansion
        tweet = client.get_tweet(
            id=post_id,
            tweet_fields=['text', 'created_at']
        )

        if not tweet or not tweet.data:
            logger.warning('Tweet not found',
                           extra={'extra_data': {'post_id': post_id}})
            return None

        logger.info('Successfully fetched post content',
                    extra={'extra_data': {
                        'post_id': post_id,
                        'text_length': len(tweet.data.text)
                    }})

        return tweet.data.text

    except tweepy.errors.NotFound:
        logger.warning('Tweet not found',
                       extra={'extra_data': {'post_id': post_id}})
        return None

    except tweepy.errors.Unauthorized:
        logger.error('Unauthorized to fetch tweet',
                     extra={'extra_data': {'post_id': post_id}})
        raise Exception('Unauthorized to access tweet. Check API credentials.')

    except tweepy.errors.Forbidden:
        logger.error('Forbidden to access tweet',
                     extra={'extra_data': {'post_id': post_id}})
        raise Exception('Forbidden to access tweet. May be private or deleted.')

    except Exception as e:
        logger.error('Error fetching tweet',
                     extra={'extra_data': {
                         'post_id': post_id,
                         'error': str(e)
                     }},
                     exc_info=True)
        raise
