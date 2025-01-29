# X Content Generator Lambda

This AWS Lambda function automatically generates and posts content to X (formerly Twitter) based on SQS messages or scheduled EventBridge events. It uses OpenAI's GPT-4 to generate engaging content based on provided prompts.

## Features

- Processes both SQS messages and EventBridge scheduled events
- Generates content using OpenAI's GPT-4
- Posts automatically to X
- Full unit test coverage
- Error handling and logging

## Prerequisites

- Python 3.9+
- AWS account with Lambda access
- OpenAI API key
- X Developer account and API credentials

## Environment Variables

The following environment variables must be set in your Lambda function:

```
OPENAI_API_KEY=your_openai_api_key
X_CONSUMER_KEY=your_x_consumer_key
X_CONSUMER_SECRET=your_x_consumer_secret
X_ACCESS_TOKEN=your_x_access_token
X_ACCESS_TOKEN_SECRET=your_x_access_token_secret
```

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Deployment

1. Create a ZIP file containing all the code and dependencies:
   ```bash
   zip -r function.zip .
   ```

2. Deploy to AWS Lambda using the AWS Console or CLI:
   ```bash
   aws lambda update-function-code --function-name YourFunctionName --zip-file fileb://function.zip
   ```

## Testing

Run the unit tests:
```bash
python -m unittest discover tests
```

## SQS Message Format

Example SQS message:
```json
{
    "topic": "technology",
    "keywords": ["AI", "future"],
    "tone": "excited"
}
```

## EventBridge Schedule Format

Example EventBridge event:
```json
{
    "time": "morning",
    "detail-type": "Scheduled Event"
}
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

MIT