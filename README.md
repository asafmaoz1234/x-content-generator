# X Content Generator Lambda

An automated pipeline that fetches the latest news about a topic, synthesizes them into a compelling narrative, and posts an engaging X (formerly Twitter) post — all running as a scheduled AWS Lambda function.

## Read more about this project: [ai-powered-x-bot](https://asafmaoz.com/projects/ai-powered-x-bot.html)

## Pipeline Overview

The pipeline runs as a single Lambda invocation triggered by **EventBridge** on a schedule. Each run executes the following steps:

```
EventBridge (cron)
  └─► lambda_handler (main.py)
        │
        ├─ 1. Source Scout Agent  (scout_runner.py)
        │     Fetch news from NewsAPI ─► Normalize ─► Deduplicate
        │     ─► Quality-filter ─► Store candidates in DynamoDB
        │
        ├─ 2. Synthesis  (synthesizer.py)
        │     Fetch unused candidates from DynamoDB ─► Synthesize
        │     angle via OpenAI ─► Validate grounding
        │
        ├─ 3. Prompt Building  (prompt_builder.py)
        │     Load prompt template ─► Inject synthesis result
        │     (or fall back to generic instructions)
        │
        ├─ 4. Content Generation  (LLM_operations.py)
        │     Call OpenAI to generate the final X post
        │
        ├─ 5. Post to X  (x_poster.py)
        │     Authenticate via OAuth 1.0a ─► Create tweet
        │
        └─ 6. Mark candidates as used in DynamoDB
```

### Key design points

- **Graceful degradation** — if the scout or synthesis steps fail, the pipeline falls back to a generic prompt and still posts.
- **Deduplication** — URL canonicalization + semantic similarity (OpenAI embeddings) prevent duplicate stories.
- **Grounding validation** — every fact in the synthesized angle is verified against the source articles.
- **TTL cleanup** — DynamoDB items expire automatically after 30 days.

## Features

- Fetches latest news via NewsAPI and stores qualified candidates in DynamoDB
- Synthesizes multiple news sources into a coherent narrative angle
- Generates engaging X posts using OpenAI (GPT-4 by default)
- Posts automatically to X via OAuth 1.0a
- Two-stage deduplication (URL + semantic similarity)
- Quality filtering with source-reputation scoring
- Full unit test coverage
- Error handling and structured logging

## Prerequisites

- Python 3.11+
- AWS account with Lambda and DynamoDB access
- OpenAI API key
- NewsAPI key ([newsapi.org](https://newsapi.org))
- X Developer account with OAuth 1.0a credentials (read + write permissions)

---

## Environment Variables

All variables are set in the **Lambda function configuration** (or in a local `.env` file for development).

### Required

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Model name (e.g. `gpt-4`, `gpt-4o`) |
| `X_CONSUMER_KEY` | X OAuth 1.0a consumer key |
| `X_CONSUMER_SECRET` | X OAuth 1.0a consumer secret |
| `X_ACCESS_TOKEN` | X OAuth 1.0a access token |
| `X_ACCESS_TOKEN_SECRET` | X OAuth 1.0a access token secret |
| `CONTENT_TOPIC` | Topic for content generation (e.g. `artificial intelligence`) |
| `CONTENT_KEYWORDS` | Comma-separated keywords to include (e.g. `AI,LLM,GPT`) |
| `CONTENT_TONE` | Desired tone (e.g. `insightful`, `excited`, `professional`) |
| `CONTENT_MIN_CHARACTERS` | Minimum post length in characters (e.g. `100`) |
| `CONTENT_MAX_CHARACTERS` | Maximum content length for generation (e.g. `1500`) - affects token limit |
| `NEWSAPI_API_KEY` | NewsAPI.org API key |
| `NEWS_CANDIDATES_TABLE` | DynamoDB table name for news candidates |

### Optional (Source Scout tuning)

| Variable | Default | Range | Description |
|---|---|---|---|
| `NEWS_TIME_WINDOW_HOURS` | `24` | 1–168 | How far back to fetch news (hours) |
| `NEWS_MIN_RELEVANCE_SCORE` | `0.6` | 0.0–1.0 | Minimum LLM-scored relevance to keep a candidate |
| `NEWS_MIN_QUALITY_SCORE` | `0.5` | 0.0–1.0 | Minimum composite quality score |
| `NEWS_SIMILARITY_THRESHOLD` | `0.92` | 0.0–1.0 | Cosine-similarity threshold for semantic dedup |
| `NEWS_MAX_CANDIDATES` | `20` | 1–100 | Max candidates to fetch per run |

---

## DynamoDB Setup

### Table: News Candidates

Create a DynamoDB table with the name you set in `NEWS_CANDIDATES_TABLE`.

#### Primary Key

| Key | Type | Description |
|---|---|---|
| `canonical_url` (Partition Key) | String | Canonicalized article URL |
| `topic` (Sort Key) | String | Topic tag (matches `CONTENT_TOPIC`) |

#### Global Secondary Index (GSI)

| Index Name | Partition Key | Sort Key |
|---|---|---|
| `topic-published_at-index` | `topic` (String) | `published_at` (String, ISO 8601) |

This GSI is used for querying recent unused candidates and fetching embeddings for deduplication.

#### Item Attributes

| Attribute | Type | Description |
|---|---|---|
| `canonical_url` | String | Canonicalized URL (partition key) |
| `original_url` | String | Original URL from NewsAPI |
| `title` | String | Article title |
| `description` | String | Article description / snippet |
| `source_name` | String | Publisher name (e.g. "TechCrunch") |
| `source_domain` | String | Publisher domain (e.g. "techcrunch.com") |
| `published_at` | String | Article publish time (ISO 8601) |
| `fetched_at` | String | Time the article was fetched (ISO 8601) |
| `language` | String | Language code (default: `en`) |
| `topic` | String | Topic tag (sort key) |
| `relevance_score` | Number | LLM-scored relevance (0.0–1.0) |
| `quality_score` | Number | Composite quality score (0.0–1.0) |
| `embedding` | List\<Number\> | OpenAI embedding vector (`text-embedding-3-small`) |
| `status` | String | `new` or `used` |
| `expires_at` | Number | TTL timestamp (epoch seconds, 30 days from creation) |

#### TTL Configuration

Enable **Time to Live** on the `expires_at` attribute so items are automatically deleted after 30 days.

#### AWS CLI Quick-Create

```bash
# Create the table
aws dynamodb create-table \
  --table-name YOUR_TABLE_NAME \
  --attribute-definitions \
      AttributeName=canonical_url,AttributeType=S \
      AttributeName=topic,AttributeType=S \
      AttributeName=published_at,AttributeType=S \
  --key-schema \
      AttributeName=canonical_url,KeyType=HASH \
      AttributeName=topic,KeyType=RANGE \
  --global-secondary-indexes \
      '[{
          "IndexName": "topic-published_at-index",
          "KeySchema": [
              {"AttributeName": "topic", "KeyType": "HASH"},
              {"AttributeName": "published_at", "KeyType": "RANGE"}
          ],
          "Projection": {"ProjectionType": "ALL"},
          "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
      }]' \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5

# Enable TTL
aws dynamodb update-time-to-live \
  --table-name YOUR_TABLE_NAME \
  --time-to-live-specification Enabled=true,AttributeName=expires_at
```

> **Tip:** For production workloads consider using on-demand capacity mode instead of provisioned.

---

## IAM Permissions

The Lambda execution role needs the following DynamoDB permissions on the news-candidates table (and its GSI):

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:BatchGetItem",
    "dynamodb:Query",
    "dynamodb:UpdateItem"
  ],
  "Resource": [
    "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/YOUR_TABLE_NAME",
    "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/YOUR_TABLE_NAME/index/*"
  ]
}
```

The role also needs the default `AWSLambdaBasicExecutionRole` for CloudWatch Logs.

---

## External APIs

| Service | Library | Purpose |
|---|---|---|
| **NewsAPI** | `newsapi-python` | Fetch latest news articles for the configured topic |
| **OpenAI** | `openai` | Embeddings (`text-embedding-3-small`), relevance classification, synthesis, and content generation |
| **X (Twitter)** | `tweepy` | Post tweets via OAuth 1.0a |
| **AWS DynamoDB** | `boto3` | Store and query news candidates |

---

## Installation

1. Clone this repository
2. Install dependencies for local development:

```bash
pip install -r requirements.txt
```

3. Copy `.env.template` to `.env` and fill in your credentials:

```bash
cp .env.template .env
```

---

## Deployment

### Creating the Lambda Deployment Package

#### Preferred Method

1. Grant execute permission to the build script (one time):

```bash
chmod +x build-project/build-dep-zip.sh
```

2. Run the build script:

```bash
./build-project/build-dep-zip.sh
```

3. Use the generated `function.zip` for deployment.

#### Manual Method

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
   openai tweepy newsapi-python boto3
```

3. Copy the Lambda function files:

```bash
cp ../main.py .
cp ../prompt_builder.py .
cp ../x_poster.py .
cp ../LLM_operations.py .
cp ../scout_runner.py .
cp ../synthesizer.py .
cp ../prompts/social_media_prompt.txt ./prompts/
cp ../prompts/synthesis_prompt.txt ./prompts/
cp -r ../source_scout .
```

4. Create the deployment ZIP file:

```bash
zip -r ../function.zip .
```

### Deploying to AWS Lambda

1. Create a new Lambda function in AWS Console:
   - Runtime: Python 3.11
   - Handler: `main.lambda_handler`
   - Architecture: x86_64

2. Upload the deployment package:
   - Go to the Lambda console
   - Select your function
   - Click "Upload from" -> ".zip file"
   - Upload your `function.zip`

3. Configure all **required** environment variables (see table above)

4. Set up an **EventBridge** rule with a cron schedule (e.g. `rate(6 hours)`) targeting the Lambda function

---

## Testing

### Local Testing

Run the unit tests:

```bash
python -m pytest tests/ -v
```

### AWS Lambda Test Event

EventBridge invocations use the env parameters to generate the prompt. A minimal test event:

```json
{
  "source": "aws.events",
  "detail-type": "Scheduled Event",
  "id": "test-event-001"
}
```

---

## Project Structure

```
x-content-gen/
├── main.py                  # Lambda entry point (lambda_handler)
├── scout_runner.py          # Orchestrates the Source Scout pipeline
├── synthesizer.py           # Synthesises news candidates into a narrative angle
├── prompt_builder.py        # Builds the final LLM prompt
├── LLM_operations.py        # OpenAI content-generation with retry
├── x_poster.py              # Posts content to X via Tweepy
├── source_scout/            # Source Scout agent package
│   ├── __init__.py
│   ├── config.py            # ScoutConfig (loads & validates env vars)
│   ├── fetcher.py           # NewsAPI client
│   ├── normalizer.py        # Article normalisation → NewsCandidate
│   ├── dedup.py             # URL canonicalization + semantic dedup
│   ├── quality_filter.py    # Source reputation & relevance scoring
│   └── store.py             # DynamoDB CRUD operations
├── prompts/
│   ├── social_media_prompt.txt   # X post generation prompt template
│   └── synthesis_prompt.txt      # News synthesis prompt template
├── tests/
│   ├── test_source_scout.py
│   └── test_synthesizer.py
├── build-project/
│   └── build-dep-zip.sh     # Lambda deployment package builder
├── requirements.txt
├── .env.template
└── README.md
```

---

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

MIT
