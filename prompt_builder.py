import openai
import os

# Load OpenAI API Key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_tweet(data):
    """
    Generates a tweet based on input data.
    """
    prompt = f"Write a concise, engaging tweet about {data['topic']} in a casual tone."

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50
    )

    tweet = response["choices"][0]["message"]["content"].strip()
    return tweet
