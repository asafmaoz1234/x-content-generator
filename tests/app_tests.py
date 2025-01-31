import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
from main import lambda_handler
from prompt_builder import build_prompt
from x_poster import post_to_x


class TestContentGenerator(unittest.TestCase):
    def setUp(self):
        # Sample prompt template for testing
        self.prompt_template = """
        You are a social media content creator.
        Create a social media post about {topic}.
        Keywords to include: {keywords}
        Tone: {tone}
        """

        # Sample events
        self.sqs_event = {
            'Records': [{
                'body': json.dumps({
                    'topic': 'technology',
                    'keywords': ['AI', 'future'],
                    'tone': 'excited'
                })
            }]
        }

        self.schedule_event = {
            'time': 'morning',
            'topic': 'daily update',
            'detail-type': 'Scheduled Event'
        }

        # Set up environment variable patches
        self.env_patcher = patch.dict('os.environ', {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MODEL': 'gpt-4',
            'CONTENT_TOPIC': 'sample topic',
            'CONTENT_KEYWORDS': 'word1, word2, word3',
            'CONTENT_TONE': 'conversational, witty, insightful',
            'CONTENT_MIN_CHARACTERS': '100',
            'X_CONSUMER_KEY': 'test-consumer-key',
            'X_CONSUMER_SECRET': 'test-consumer-secret',
            'X_ACCESS_TOKEN': 'test-access-token',
            'X_ACCESS_TOKEN_SECRET': 'test-access-token-secret'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('main.openai')
    @patch('main.post_to_x')
    @patch('builtins.open', new_callable=mock_open)
    def test_lambda_handler_sqs(self, mock_file, mock_post_to_x, mock_openai):
        # Mock file reading
        mock_file.return_value.read.return_value = self.prompt_template

        # Mock OpenAI response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Test content"))]
        mock_openai.chat.completions.create.return_value = mock_completion

        # Mock X posting
        mock_post_to_x.return_value = "12345"

        # Execute handler
        response = lambda_handler(self.sqs_event, MagicMock())

        # Verify response
        self.assertEqual(response['statusCode'], 200)
        response_body = json.loads(response['body'])
        self.assertIn('Successfully posted to X', response_body['message'])

        # Verify OpenAI was called with correct model
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'gpt-4')

        # Verify post_to_x was called
        mock_post_to_x.assert_called_once_with("Test content")

    @patch('main.openai')
    @patch('main.post_to_x')
    @patch('builtins.open', new_callable=mock_open)
    def test_lambda_handler_schedule(self, mock_file, mock_post_to_x, mock_openai):
        # Mock file reading
        mock_file.return_value.read.return_value = self.prompt_template

        # Mock OpenAI response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Test content"))]
        mock_openai.chat.completions.create.return_value = mock_completion

        # Mock X posting
        mock_post_to_x.return_value = "12345"

        # Execute handler
        response = lambda_handler(self.schedule_event, MagicMock())

        # Verify response
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('post_id', json.loads(response['body']))

    def test_build_prompt_sqs(self):
        message = json.loads(self.sqs_event['Records'][0]['body'])
        prompt = build_prompt(message, 'sqs', self.prompt_template)

        self.assertIn('technology', prompt)
        self.assertIn('AI', prompt)
        self.assertIn('excited', prompt)

    @patch('x_poster.tweepy')
    def test_post_to_x(self, mock_tweepy):
        # Mock tweepy client
        mock_client = MagicMock()
        mock_client.create_tweet.return_value = MagicMock(
            data={'id': '12345'}
        )
        mock_tweepy.Client.return_value = mock_client

        # Test posting
        tweet_id = post_to_x("Test content")

        # Verify result
        self.assertEqual(tweet_id, '12345')
        mock_client.create_tweet.assert_called_once_with(text="Test content")

    def test_environment_variables(self):
        required_vars = [
            'OPENAI_API_KEY',
            'OPENAI_MODEL',
            'X_CONSUMER_KEY',
            'X_CONSUMER_SECRET',
            'X_ACCESS_TOKEN',
            'X_ACCESS_TOKEN_SECRET'
        ]

        for var in required_vars:
            self.assertIn(var, os.environ)

    def test_build_prompt_schedule(self):
        prompt = build_prompt(self.schedule_event, 'schedule', self.prompt_template)
        self.assertIn('sample topic', prompt)

    @patch('main.openai')
    @patch('main.post_to_x')
    @patch('builtins.open')
    def test_lambda_handler_file_error(self, mock_file, mock_post_to_x, mock_openai):
        # Mock file reading error
        mock_file.side_effect = FileNotFoundError("Prompt template not found")

        # Create a proper mock response structure for OpenAI
        class MockChoice:
            def __init__(self):
                self.message = type('Message', (), {'content': 'Test content'})()

        class MockResponse:
            def __init__(self):
                self.choices = [MockChoice()]

        mock_openai.chat.completions.create.return_value = MockResponse()
        mock_post_to_x.return_value = "12345"  # Return a string ID for the tweet

        # Execute handler - should still work with fallback prompt
        response = lambda_handler(self.sqs_event, MagicMock())

        # Verify response
        self.assertEqual(response['statusCode'], 200)
        response_body = json.loads(response['body'])  # Make sure we can parse the JSON
        self.assertIn('content', response_body)
        self.assertIn('post_id', response_body)
        self.assertTrue(mock_openai.chat.completions.create.called)
        self.assertTrue(mock_post_to_x.called)

if __name__ == '__main__':
    unittest.main()