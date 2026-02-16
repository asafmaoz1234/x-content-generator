import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def build_prompt(event: Dict[Any, Any], template: str, synthesis_result=None) -> str:
    """
    Builds a prompt for OpenAI based on the event data, template, and optional synthesis result.
    
    Args:
        event: Event data dictionary
        template: Prompt template string
        synthesis_result: Optional SynthesisResult from synthesizer module
        
    Returns:
        Formatted prompt string
    """
    logger.info('Starting prompt building')

    # Extract configuration from environment variables
    topic = os.environ['CONTENT_TOPIC']
    keywords = os.environ['CONTENT_KEYWORDS']
    tone = os.environ['CONTENT_TONE']
    min_char_count = os.environ['CONTENT_MIN_CHARACTERS']
    max_char_count = os.environ['CONTENT_MAX_CHARACTERS']

    # Prepare template variables
    template_vars = {
        'topic': topic,
        'keywords': keywords,
        'tone': tone,
        'min_char_count': min_char_count,
        'max_char_count': max_char_count
    }
    
    # If synthesis result provided, add synthesis data to template vars
    if synthesis_result:
        logger.info('Including synthesis data in prompt')
        
        # Format key facts as numbered list
        key_facts_formatted = []
        for i, fact in enumerate(synthesis_result.key_facts, 1):
            key_facts_formatted.append(f"{i}. {fact.fact} (Source: {fact.source_name})")
        
        # Build synthesis instructions section
        synthesis_instructions = f"""
**SYNTHESIZED ANGLE (from real news sources):**
{synthesis_result.angle}

**SUGGESTED HOOK:**
{synthesis_result.hook}

**KEY FACTS (use these, they're from verified sources):**
{chr(10).join(key_facts_formatted) if key_facts_formatted else 'None'}

**DRAFT POST (refine this to perfection):**
{synthesis_result.draft_post}

YOUR TASK: Review the draft post above and refine it to be perfect. Ensure it:
- Uses the factual content from the key facts
- Maintains the hook and angle
- Stays within the character limit
- Is engaging and optimized for X
"""
        
        template_vars['synthesis_instructions'] = synthesis_instructions
        
        logger.info('Building prompt with synthesis', extra={'extra_data': {
            'topic': topic,
            'angle': synthesis_result.angle[:100],
            'num_facts': len(synthesis_result.key_facts)
        }})
    else:
        logger.info('Building prompt without synthesis (generic mode)')
        
        # Generic instructions when no synthesis available
        synthesis_instructions = f"""
**NO SYNTHESIS DATA AVAILABLE**

Create an engaging post about {topic} based on general knowledge.
The post should describe innovative features and interesting developments in this space.
Be specific and mention concrete innovations.

YOUR TASK: Create an original, engaging post from scratch.
"""
        
        template_vars['synthesis_instructions'] = synthesis_instructions

    # Format the template with the message data
    formatted_prompt = template.format(**template_vars)

    logger.info('Prompt building completed')
    return formatted_prompt
