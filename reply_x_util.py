import os
import requests
from typing import List, Dict
from logger_util import logger


def fetch_replies_to_post(post_id: str, original_author_id: str) -> List[Dict]:
    """
    Fetches recent replies to a post and identifies threads where someone other
    than the original poster was the last to reply.

    Args:
        post_id: The ID of the post to fetch replies for
        original_author_id: The ID of the original post's author

    Returns:
        List of reply threads where someone else was last to reply
    """
    try:
        logger.info('Fetching replies',
                    extra={'extra_data': {
                        'post_id': post_id,
                        'original_author_id': original_author_id
                    }})

        headers = {"Authorization": f"Bearer {os.environ['X_BEARER_TOKEN']}"}

        # Fetch replies
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": f"conversation_id:{post_id}",
            "tweet.fields": "author_id,created_at,in_reply_to_user_id,conversation_id,referenced_tweets",
            "max_results": 100,
            "user.fields": "username"
        }

        response = requests.get(search_url, headers=headers, params=params)

        if response.status_code != 200:
            logger.error('Failed to fetch replies',
                         extra={'extra_data': {
                             'status_code': response.status_code,
                             'response': response.text
                         }})
            return []

        result = response.json()

        if 'data' not in result:
            logger.info('No replies found',
                        extra={'extra_data': {'post_id': post_id}})
            return []

        # Group replies by their parent tweet to form threads
        reply_threads = {}
        for reply in result['data']:
            # Get the parent tweet ID from referenced_tweets
            parent_id = None
            if 'referenced_tweets' in reply:
                for ref in reply['referenced_tweets']:
                    if ref['type'] == 'replied_to':
                        parent_id = ref['id']
                        break

            if parent_id:
                if parent_id not in reply_threads:
                    reply_threads[parent_id] = []
                reply_threads[parent_id].append(reply)

        # Sort replies in each thread by creation time
        for thread in reply_threads.values():
            thread.sort(key=lambda x: x['created_at'])

        # Filter threads where original poster was last to reply
        op_last_replies = []
        for thread in reply_threads.values():
            if thread and thread[-1]['author_id'] == original_author_id:
                op_last_replies.append(thread)

        # Filter threads where someone else was last to reply
        others_last_replies = []
        for thread in reply_threads.values():
            if thread and thread[-1]['author_id'] != original_author_id:
                others_last_replies.append(thread)

        # Print all replies for debugging
        print("\nAll replies found:")
        for reply in result['data']:
            print(f"ID: {reply['id']}")
            print(f"Author ID: {reply['author_id']}")
            print(f"Text: {reply['text']}")
            print("---")

        print("\nThreads where original poster was last to reply:")
        for thread in op_last_replies:
            print(f"\nThread with {len(thread)} replies:")
            for reply in thread:
                print(f"ID: {reply['id']}")
                print(f"Author ID: {reply['author_id']}")
                print(f"Text: {reply['text']}")
                print("---")

        # Print threads where OP was last to reply
        print("\nThreads requiring response (OP was not last to reply):")
        for thread in others_last_replies:
            print(f"\nThread with {len(thread)} replies:")
            for reply in thread:
                print(f"ID: {reply['id']}")
                print(f"Author ID: {reply['author_id']}")
                print(f"Text: {reply['text']}")
                print("---")

        return others_last_replies

    except Exception as e:
        logger.error('Error processing replies',
                     extra={'extra_data': {
                         'post_id': post_id,
                         'error': str(e)
                     }},
                     exc_info=True)
        raise
