from typing import Dict, Any


def build_prompt(message: Dict[Any, Any], event_type: str) -> str:
    """
    Builds a prompt for OpenAI based on the event data.
    
    Args:
        message: The message data from SQS or EventBridge
        event_type: Type of event ('sqs' or 'schedule')
        
    Returns:
        str: Generated prompt for OpenAI
    """
    if event_type == 'sqs':
        # Extract relevant fields from SQS message
        topic = message.get('topic', 'general')
        keywords = message.get('keywords', [])
        tone = message.get('tone', 'professional')

        prompt = f"""
        Create a social media post about {topic}.
        Keywords to include: {', '.join(keywords)}
        Tone: {tone}
        Keep the content engaging and within X's character limit.
        """

    else:  # schedule event
        current_hour = message.get('time', 'morning')
        prompt = f"""
        Create a {current_hour} social media post that would engage our audience.
        Include trending topics if relevant.
        Keep the content engaging and within X's character limit.
        """

    return prompt.strip()
