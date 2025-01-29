from typing import Dict, Any
from logger_util import logger


def build_prompt(message: Dict[Any, Any], event_type: str) -> str:
    """
    Builds a prompt for OpenAI based on the event data.
    """
    logger.info('Starting prompt building',
                extra={'extra_data': {'event_type': event_type}})

    if event_type == 'sqs':
        # Extract relevant fields from SQS message
        topic = message.get('topic', 'general')
        keywords = message.get('keywords', [])
        tone = message.get('tone', 'professional')

        logger.info('Building SQS prompt',
                    extra={'extra_data': {
                        'topic': topic,
                        'keywords': keywords,
                        'tone': tone
                    }})

        prompt = f"""
        Create a social media post about {topic}.
        Keywords to include: {', '.join(keywords)}
        Tone: {tone}
        Keep the content engaging and within X's character limit.
        """

    else:  # schedule event
        current_hour = message.get('time', 'morning')
        logger.info('Building scheduled prompt',
                    extra={'extra_data': {'time': current_hour}})

        prompt = f"""
        Create a {current_hour} social media post that would engage our audience.
        Include trending topics if relevant.
        Keep the content engaging and within X's character limit.
        """

    final_prompt = prompt.strip()
    logger.info('Prompt building completed',
                extra={'extra_data': {'prompt_length': len(final_prompt)}})

    return final_prompt