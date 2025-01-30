from typing import Dict, Any
from logger_util import logger


def build_prompt(message: Dict[Any, Any], event_type: str, template: str) -> str:
    """
    Builds a prompt for OpenAI based on the event data and template.
    """
    logger.info('Starting prompt building',
                extra={'extra_data': {'event_type': event_type}})

    if event_type == 'sqs':
        # Extract relevant fields from SQS message
        topic = message.get('topic', 'general')
        keywords = message.get('keywords', [])
        tone = message.get('tone', 'professional')
        time_of_day = message.get('time_of_day', 'timely')

        logger.info('Building SQS prompt',
                    extra={'extra_data': {
                        'topic': topic,
                        'keywords': keywords,
                        'tone': tone,
                        'time_of_day': time_of_day
                    }})

        # Format the template with the message data
        formatted_prompt = template.format(
            topic=topic,
            keywords=', '.join(keywords),
            tone=tone,
            time_of_day=time_of_day
        )

    else:  # schedule event
        time_of_day = message.get('time', 'timely')
        topic = message.get('topic', 'general')
        logger.info('Building scheduled prompt',
                    extra={'extra_data': {
                        'time_of_day': time_of_day,
                        'topic': topic
                    }})

        # Format the template with schedule data
        formatted_prompt = template.format(
            topic=topic,
            keywords='trending topics',
            tone='professional',
            time_of_day=time_of_day
        )

    logger.info('Prompt building completed',
                extra={'extra_data': {'prompt_length': len(formatted_prompt)}})

    return formatted_prompt
