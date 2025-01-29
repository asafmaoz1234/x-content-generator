import os
import tweepy
from typing import Optional

def post_to_x(content: str) -> str:
    """
    Posts content to X using the Tweepy library.

    Args:
        content: The content to post

    Returns:
        str: ID of the posted tweet

    Raises:
        Exception: If posting fails
    """
    # Initialize X API client
    client = tweepy.Client(
        consumer_key=os.environ['X_CONSUMER_KEY'],
        consumer_secret=os.environ['X_CONSUMER_SECRET'],
        access_token=os.environ['X_ACCESS_TOKEN'],
        access_token_secret=os.environ['X_ACCESS_TOKEN_SECRET']
    )

    # Post to X
    response = client.create_tweet(text=content)

    return response.data['id']