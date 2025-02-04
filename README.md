# X Content Generator Lambda

This AWS Lambda function automatically generates and posts content to X (formerly Twitter) based on SQS messages or scheduled EventBridge events. It uses OpenAI's GPT-4 to generate engaging content based on provided prompts.

## Features

- Processes both SQS messages and EventBridge scheduled events
- Generates content using OpenAI's GPT-4
- Posts automatically to X
- Full unit test coverage
- Error handling and logging

## Prerequisites

- Python 3.11+
- AWS account with Lambda access
- OpenAI API key
- X Developer account and API credentials

## Environment Variables

The following environment variables must be set in your Lambda function:

```
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4  # or gpt-3.5-turbo, etc.
X_CONSUMER_KEY=your_x_consumer_key
X_CONSUMER_SECRET=your_x_consumer_secret
X_ACCESS_TOKEN=your_x_access_token
X_ACCESS_TOKEN_SECRET=your_x_access_token_secret
CONTENT_KEYWORDS=keywords_to_include  # comma-separated list of keywords
CONTENT_MIN_CHARACTERS=minimum_characters  # minimum content length
CONTENT_TONE=content_tone  # tone of the content
CONTENT_TOPIC=content_topic  # topic of the content
```

## Installation

1. Clone this repository
2. Install dependencies for local development:
   ```bash
   pip install -r requirements.txt
   ```

## Deployment

### Creating the Lambda Deployment Package
#### Preferred Method:
1. grant execute permission to the build script (one time):
   ```bash
   chmod +x build-dep-zip.sh
   ```
2. Run the build script:
```bash
./build-dep-zip
```
3. use the generated function.zip file for deployment

#### Manual Method:
1. Create a fresh directory for your deployment package:
   ```bash
   mkdir -p deployment-package/prompts
   cd deployment-package
   ```

2. Install dependencies for AWS Lambda (Linux):
   ```bash
   pip install --platform manylinux2014_x86_64 \
      --implementation cp \
      --python-version 3.11 \
      --only-binary=:all: \
      --target . \
      openai tweepy python-json-logger
   ```

3. Copy the Lambda function files:
   ```bash
   cp ../main.py .
   cp ../prompt_builder.py .
   cp ../x_poster.py .
   cp ../logger_util.py .
   cp ../prompts/social_media_prompt.txt ./prompts/
   ```

4. Create the deployment ZIP file:
   ```bash
   zip -r ../function.zip .
   ```

### Alternative: Using Docker for Deployment Package

If you're on Windows or experiencing issues with the direct installation method:

1. Create a Dockerfile:
   ```dockerfile
   FROM public.ecr.aws/lambda/python:3.11
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY main.py .
   COPY prompt_builder.py .
   COPY x_poster.py .
   COPY logger_util.py .
   COPY prompts/social_media_prompt.txt ./prompts/
   
   RUN zip -r function.zip .
   ```

2. Build and run:
   ```bash
   docker build -t lambda-builder .
   docker run --name lambda-builder lambda-builder
   docker cp lambda-builder:/function.zip .
   ```

### Deploying to AWS Lambda

1. Create a new Lambda function in AWS Console:
   - Runtime: Python 3.11
   - Handler: main.lambda_handler
   - Architecture: x86_64

2. Upload the deployment package:
   - Go to the Lambda console
   - Select your function
   - Click "Upload from" → ".zip file"
   - Upload your function.zip

3. Configure environment variables in AWS Console

4. Set up triggers (SQS/EventBridge) as needed

## Testing

### Local Testing
Run the unit tests:
```bash
python -m unittest discover tests
```

### AWS Lambda Test Events

- SQS message test event:
```json
{
    "Records": [{
        "body": "{\"topic\":\"technology\",\"keywords\":[\"AI\",\"future\"],\"tone\":\"excited\",\"min_char_count\":\"100\"}"
    }]
}
```

- EventBridge uses the env parameters to generate the prompt:


## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

MIT