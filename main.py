import json
import os
from typing import Dict, Any
import openai
from datetime import datetime

from prompt_builder import build_prompt
from x_post_util import post_to_x


def lambda_handler(event: Dict[Any, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler that processes SQS messages or EventBridge events,
    generates content using OpenAI, and posts to X.
    """
    try:
        # Initialize OpenAI client
        openai.api_key = os.environ['OPENAI_API_KEY']

        # Determine event source and extract relevant data
        if 'Records' in event:  # SQS event
            message = json.loads(event['Records'][0]['body'])
            event_type = 'sqs'
        else:  # EventBridge scheduled event
            message = event
            event_type = 'schedule'

        # Build prompt based on event data
        prompt = build_prompt(message, event_type)

        # Generate content using OpenAI
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a social media content creator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=280,  # X character limit
            temperature=0.7
        )

        # Extract generated content
        content = response.choices[0].message.content.strip()

        # Post to X
        post_to_x(content)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully posted to X',
                'content': content,
                'timestamp': datetime.utcnow().isoformat()
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }