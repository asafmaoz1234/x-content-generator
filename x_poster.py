import tweepy
from logger_util import logger


def post_to_x(client: tweepy.Client, content: str, reply_id: str = None) -> str:
    """
    Posts content to X using the Tweepy library.
    """

    try:
        logger.info('Validating API credentials and permissions')
        try:
            # Test API credentials by getting account info
            me = client.get_me()
            logger.info('Basic API credentials validated',
                        extra={'extra_data': {'username': me.data.username}})

        except tweepy.errors.Unauthorized:
            logger.error('Invalid API credentials')
            raise Exception('Invalid X API credentials. Please check your keys and tokens.')
        except tweepy.errors.Forbidden as e:
            error_msg = str(e)
            if 'write' in error_msg.lower():
                logger.error('Missing write permissions',
                             extra={'extra_data': {'error': error_msg}})
                raise Exception(
                    'Your app lacks write permissions. Please enable write permissions '
                    'in the Twitter Developer Portal and regenerate your tokens.'
                )
            else:
                logger.error(f'API permission error: {error_msg}')
                raise Exception(
                    'X API permission error. Please check your app permissions '
                    'in the Twitter Developer Portal.'
                )
        # Post actual content to X
        try:
            logger.info('Posting content to X',
                        extra={'extra_data': {'content': content}})

            post_details = {}
            # add details to post a response to a tweet
            if reply_id:
                post_details['in_reply_to_tweet_id'] = reply_id
            post_details['text'] = content

            logger.info('Posting content to X',
                        extra={'extra_data': {'content': post_details['text']}})
            response = client.create_tweet(**post_details)

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
            raise Exception(
                f'Failed to post tweet. Error: {str(e)}. '
                'Please verify your app has write permissions enabled.'
            )

    except Exception as e:
        logger.error('Error in X posting process',
                     extra={'extra_data': {'error': str(e)}},
                     exc_info=True)
        raise
