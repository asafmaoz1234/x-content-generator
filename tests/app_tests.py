import unittest
from unittest.mock import patch, MagicMock
import json
from main import lambda_handler
from prompt_builder import build_prompt
from x_post_util import post_to_x

class TestContentGenerator(unittest.TestCase):
    def setUp(self):
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
            'detail-type': 'Scheduled Event'
        }

    @patch('main.openai')
    @patch('main.post_to_x')
    def test_lambda_handler_sqs(self, mock_post_to_x, mock_openai):
        # Mock OpenAI response
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test content"))]
        )

        # Mock X posting
        mock_post_to_x.return_value = "12345"

        response = lambda_handler(self.sqs_event, None)

        self.assertEqual(response['statusCode'], 200)
        self.assertIn('Successfully posted to X', response['body'])
        mock_post_to_x.assert_called_once_with("Test content")

    def test_build_prompt_sqs(self):
        message = json.loads(self.sqs_event['Records'][0]['body'])
        prompt = build_prompt(message, 'sqs')

        self.assertIn('technology', prompt)
        self.assertIn('AI', prompt)
        self.assertIn('excited', prompt)

    def test_build_prompt_schedule(self):
        prompt = build_prompt(self.schedule_event, 'schedule')

        self.assertIn('morning', prompt)
        self.assertIn('social media post', prompt)

    @patch('x_post_util.tweepy')
    def test_post_to_x(self, mock_tweepy):
        mock_client = MagicMock()
        mock_client.create_tweet.return_value = MagicMock(
            data={'id': '12345'}
        )
        mock_tweepy.Client.return_value = mock_client

        tweet_id = post_to_x("Test content")

        self.assertEqual(tweet_id, '12345')
        mock_client.create_tweet.assert_called_once_with(text="Test content")

if __name__ == '__main__':
    unittest.main()