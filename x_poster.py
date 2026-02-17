import os
import tweepy
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

MAX_TWEET_LENGTH = 280


def _split_into_chunks(content: str, max_length: int) -> list:
    """
    Split content into chunks that each fit within max_length.
    Splits at paragraph breaks first, then sentence boundaries, then word boundaries.
    """
    if len(content) <= max_length:
        return [content]

    chunks = []
    remaining = content.strip()

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        candidate = remaining[:max_length]

        # Try paragraph break (\n\n) first
        split_at = candidate.rfind('\n\n')
        if split_at > max_length // 4:
            split_at += 1  # include one newline in current chunk
        else:
            # Try sentence boundary (". " / "! " / "? " or followed by newline)
            best_sentence = -1
            for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                pos = candidate.rfind(sep)
                if pos > best_sentence:
                    best_sentence = pos + 1  # include the punctuation mark

            if best_sentence > max_length // 4:
                split_at = best_sentence
            else:
                # Fall back to word boundary
                space_pos = candidate.rfind(' ')
                if space_pos > max_length // 4:
                    split_at = space_pos
                else:
                    split_at = max_length  # force split (extremely long word)

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    return chunks


def split_into_thread(content: str) -> list:
    """
    Split content into tweet-sized chunks for a thread.
    Appends a position indicator like (1/3) to each tweet.
    Returns a list of tweet texts, each within the character limit.
    """
    if len(content) <= MAX_TWEET_LENGTH:
        return [content]

    # First pass: estimate how many chunks we need so we can size the indicator
    estimated_chunks = (len(content) // (MAX_TWEET_LENGTH - 7)) + 1
    indicator_len = len(f" ({estimated_chunks}/{estimated_chunks})")
    effective_max = MAX_TWEET_LENGTH - indicator_len

    chunks = _split_into_chunks(content, effective_max)

    # Second pass: if chunk count changed, indicator length may differ — re-split
    # Add safeguard to prevent infinite loop (max 3 iterations)
    max_iterations = 3
    iteration = 0
    actual_indicator_len = len(f" ({len(chunks)}/{len(chunks)})")
    while actual_indicator_len != indicator_len and iteration < max_iterations:
        indicator_len = actual_indicator_len
        effective_max = MAX_TWEET_LENGTH - actual_indicator_len
        chunks = _split_into_chunks(content, effective_max)
        actual_indicator_len = len(f" ({len(chunks)}/{len(chunks)})")
        iteration += 1

    total = len(chunks)
    if total <= 1:
        return chunks

    labeled = []
    for i, chunk in enumerate(chunks, 1):
        labeled.append(f"{chunk} ({i}/{total})")
    return labeled


def _create_client() -> tweepy.Client:
    """Create and return an authenticated Tweepy client."""
    return tweepy.Client(
        consumer_key=os.environ['X_CONSUMER_KEY'],
        consumer_secret=os.environ['X_CONSUMER_SECRET'],
        access_token=os.environ['X_ACCESS_TOKEN'],
        access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET']
    )


def _validate_credentials(client: tweepy.Client) -> None:
    """Validate API credentials and permissions. Raises on failure."""
    try:
        me = client.get_me()
        logger.info('API credentials validated', extra={'extra_data': {'username': me.data.username}})
    except tweepy.errors.Unauthorized:
        logger.error('Invalid API credentials')
        raise Exception('Invalid X API credentials. Please check your keys and tokens.')
    except tweepy.errors.Forbidden as e:
        error_msg = str(e)
        if 'write' in error_msg.lower():
            logger.error('Missing write permissions', extra={'extra_data': {'error': error_msg}})
            raise Exception(
                'Your app lacks write permissions. Please enable write permissions '
                'in the Twitter Developer Portal and regenerate your tokens.'
            )
        logger.error('API permission error: %s', error_msg)
        raise Exception(
            'X API permission error. Please check your app permissions '
            'in the Twitter Developer Portal.'
        )


def _post_single_tweet(client: tweepy.Client, text: str, reply_to_id: str = None) -> str:
    """Post a single tweet, optionally as a reply. Returns the tweet ID."""
    try:
        kwargs = {'text': text}
        if reply_to_id:
            kwargs['in_reply_to_tweet_id'] = reply_to_id

        response = client.create_tweet(**kwargs)
        return response.data['id']

    except tweepy.errors.Forbidden as e:
        logger.error(
            'Error posting tweet: %s',
            str(e),
            extra={'extra_data': {
                'error_code': getattr(e, 'api_codes', []),
                'error_messages': getattr(e, 'api_messages', [])
            }}
        )
        raise Exception(
            'Failed to post tweet. Error: %s. '
            'Please verify your app has write permissions enabled.' % str(e)
        )


def post_to_x(content: str) -> str:
    """
    Posts content to X using the Tweepy library.
    If the content exceeds the tweet character limit it is automatically
    split and posted as a thread (each tweet replies to the previous one).

    Returns the ID of the first (or only) tweet.
    """
    logger.info('Initializing X API client to post content: %s', content)

    try:
        client = _create_client()

        logger.info('Validating API credentials and permissions')
        _validate_credentials(client)

        tweets = split_into_thread(content)

        if len(tweets) == 1:
            logger.info('Posting single tweet to X', extra={'extra_data': {'content': content}})
            post_id = _post_single_tweet(client, tweets[0])
            logger.info('Successfully posted to X', extra={'extra_data': {'post_id': post_id}})
            return post_id

        # Multi-tweet thread
        logger.info(
            'Content exceeds %d chars — posting as thread with %d tweets',
            MAX_TWEET_LENGTH, len(tweets)
        )

        post_ids = []
        previous_id = None

        for i, tweet_text in enumerate(tweets, 1):
            tweet_id = _post_single_tweet(client, tweet_text, reply_to_id=previous_id)
            post_ids.append(tweet_id)
            previous_id = tweet_id
            logger.info(
                'Posted thread tweet %d/%d',
                i, len(tweets),
                extra={'extra_data': {'tweet_id': tweet_id}}
            )

        logger.info(
            'Successfully posted thread with %d tweets',
            len(post_ids),
            extra={'extra_data': {'post_ids': post_ids}}
        )
        return post_ids[0]

    except Exception as e:
        logger.error(
            'Error in X posting process',
            extra={'extra_data': {'error': str(e)}},
            exc_info=True
        )
        raise
