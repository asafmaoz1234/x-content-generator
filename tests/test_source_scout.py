"""
Unit tests for Source Scout Agent modules.
"""
import unittest
from unittest.mock import Mock, patch
from decimal import Decimal

# Import modules to test
from source_scout.config import ScoutConfig
from source_scout.normalizer import NewsCandidate, normalize_articles, extract_domain
from source_scout.dedup import canonicalize_url, cosine_similarity, generate_embeddings
from source_scout.quality_filter import (
    get_source_reputation,
    check_title_clarity,
    classify_relevance_batch
)
from source_scout.store import (
    _convert_floats_to_decimals,
    _convert_decimals_to_floats,
    save_candidates,
    get_existing_urls
)
from source_scout.fetcher import fetch_news


class TestConfig(unittest.TestCase):
    """Test configuration loading."""
    
    @patch.dict('os.environ', {
        'NEWSAPI_API_KEY': 'test_newsapi_key',
        'NEWS_CANDIDATES_TABLE': 'test_table',
        'CONTENT_TOPIC': 'AI tools',
        'OPENAI_API_KEY': 'test_openai_key',
        'OPENAI_MODEL': 'gpt-4',
        'NEWS_TIME_WINDOW_HOURS': '48',
        'NEWS_MIN_RELEVANCE_SCORE': '0.7',
        'NEWS_MIN_QUALITY_SCORE': '0.6',
        'NEWS_SIMILARITY_THRESHOLD': '0.95',
        'NEWS_MAX_CANDIDATES': '30'
    })
    def test_config_from_env(self):
        """Test loading config from environment variables."""
        config = ScoutConfig.from_env()
        
        self.assertEqual(config.newsapi_api_key, 'test_newsapi_key')
        self.assertEqual(config.news_candidates_table, 'test_table')
        self.assertEqual(config.topic, 'AI tools')
        self.assertEqual(config.openai_api_key, 'test_openai_key')
        self.assertEqual(config.openai_model, 'gpt-4')
        self.assertEqual(config.time_window_hours, 48)
        self.assertEqual(config.min_relevance_score, 0.7)
        self.assertEqual(config.min_quality_score, 0.6)
        self.assertEqual(config.similarity_threshold, 0.95)
        self.assertEqual(config.max_candidates, 30)
    
    @patch.dict('os.environ', {
        'NEWSAPI_API_KEY': 'test_key',
        'NEWS_CANDIDATES_TABLE': 'test_table',
        'CONTENT_TOPIC': 'AI',
        'OPENAI_API_KEY': 'test_openai',
        'NEWS_TIME_WINDOW_HOURS': '200'  # Invalid: > 168
    })
    def test_config_validation_fails(self):
        """Test that invalid config values raise ValueError."""
        with self.assertRaises(ValueError):
            ScoutConfig.from_env()


class TestNormalizer(unittest.TestCase):
    """Test article normalization."""
    
    def test_extract_domain(self):
        """Test domain extraction from URLs."""
        self.assertEqual(extract_domain('https://www.techcrunch.com/article'), 'techcrunch.com')
        self.assertEqual(extract_domain('http://example.com/path'), 'example.com')
        self.assertEqual(extract_domain('https://subdomain.example.com'), 'subdomain.example.com')
    
    def test_normalize_articles(self):
        """Test normalization of raw NewsAPI articles."""
        raw_articles = [
            {
                'url': 'https://techcrunch.com/article1',
                'title': 'Test Article 1',
                'description': 'Description 1',
                'source': {'name': 'TechCrunch'},
                'publishedAt': '2024-01-01T12:00:00Z',
                'language': 'en'
            },
            {
                'url': 'https://example.com/article2',
                'title': 'Test Article 2',
                'description': None,
                'source': {'name': 'Example'},
                'publishedAt': '2024-01-02T12:00:00Z'
            }
        ]
        
        candidates = normalize_articles(raw_articles, 'AI tools')
        
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, 'Test Article 1')
        self.assertEqual(candidates[0].description, 'Description 1')
        self.assertEqual(candidates[0].source_name, 'TechCrunch')
        self.assertEqual(candidates[0].source_domain, 'techcrunch.com')
        self.assertEqual(candidates[0].topic, 'AI tools')
        self.assertEqual(candidates[1].description, '')  # None converted to empty string
    
    def test_normalize_skips_invalid_articles(self):
        """Test that articles without required fields are skipped."""
        raw_articles = [
            {'title': 'No URL'},
            {'url': 'https://example.com'},  # No title
            {
                'url': 'https://valid.com',
                'title': 'Valid Article',
                'source': {'name': 'Valid'}
            }
        ]
        
        candidates = normalize_articles(raw_articles, 'test')
        
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, 'Valid Article')


class TestDedup(unittest.TestCase):
    """Test deduplication logic."""
    
    def test_canonicalize_url(self):
        """Test URL canonicalization."""
        # Remove tracking params
        url1 = 'https://example.com/article?utm_source=twitter&id=123'
        self.assertEqual(canonicalize_url(url1), 'https://example.com/article?id=123')
        
        # Remove www
        url2 = 'http://www.example.com/path'
        self.assertEqual(canonicalize_url(url2), 'https://example.com/path')
        
        # Remove trailing slash
        url3 = 'https://example.com/article/'
        self.assertEqual(canonicalize_url(url3), 'https://example.com/article')
        
        # Remove fragment
        url4 = 'https://example.com/article#section'
        self.assertEqual(canonicalize_url(url4), 'https://example.com/article')
        
        # Multiple tracking params
        url5 = 'https://example.com/page?utm_campaign=test&fbclid=xyz&ref=home&id=1'
        self.assertEqual(canonicalize_url(url5), 'https://example.com/page?id=1')
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        # Identical vectors
        v1 = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cosine_similarity(v1, v1), 1.0, places=5)
        
        # Orthogonal vectors
        v2 = [1.0, 0.0]
        v3 = [0.0, 1.0]
        self.assertAlmostEqual(cosine_similarity(v2, v3), 0.0, places=5)
        
        # Similar vectors
        v4 = [1.0, 2.0, 3.0]
        v5 = [1.1, 2.1, 3.1]
        similarity = cosine_similarity(v4, v5)
        self.assertGreater(similarity, 0.99)
        
        # Empty vectors
        self.assertEqual(cosine_similarity([], []), 0.0)
        self.assertEqual(cosine_similarity([1.0], []), 0.0)
    
    @patch('source_scout.dedup.openai')
    def test_generate_embeddings(self, mock_openai):
        """Test embedding generation."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6])
        ]
        mock_openai.embeddings.create.return_value = mock_response
        
        config = Mock()
        config.openai_api_key = 'test_key'
        
        texts = ['text 1', 'text 2']
        embeddings = generate_embeddings(texts, config)
        
        self.assertEqual(len(embeddings), 2)
        self.assertEqual(embeddings[0], [0.1, 0.2, 0.3])
        self.assertEqual(embeddings[1], [0.4, 0.5, 0.6])
        
        mock_openai.embeddings.create.assert_called_once()


class TestQualityFilter(unittest.TestCase):
    """Test quality filtering logic."""
    
    def test_get_source_reputation(self):
        """Test source reputation scoring."""
        self.assertEqual(get_source_reputation('techcrunch.com'), 0.95)
        self.assertEqual(get_source_reputation('reuters.com'), 0.95)
        self.assertEqual(get_source_reputation('medium.com'), 0.50)
        self.assertEqual(get_source_reputation('unknown-site.com'), 0.40)
    
    def test_check_title_clarity(self):
        """Test title clarity checks."""
        # Valid titles
        self.assertTrue(check_title_clarity('New AI Tool Revolutionizes Content Creation'))
        self.assertTrue(check_title_clarity('Study Shows 50% Improvement in Efficiency'))
        
        # Too short
        self.assertFalse(check_title_clarity('Short'))
        
        # Too long
        self.assertFalse(check_title_clarity('x' * 350))
        
        # Too many capitals
        self.assertFalse(check_title_clarity('THIS IS ALL CAPS TITLE FOR ARTICLE'))
        
        # Excessive punctuation
        self.assertFalse(check_title_clarity('Amazing news!!!'))
        self.assertFalse(check_title_clarity('What is this???'))
        
        # Clickbait patterns
        self.assertFalse(check_title_clarity('You won\'t believe what happens next'))
        self.assertFalse(check_title_clarity('SHOCKING discovery in AI research'))
        self.assertFalse(check_title_clarity('10 reasons why AI will change everything'))
    
    @patch('source_scout.quality_filter.openai')
    def test_classify_relevance_batch(self, mock_openai):
        """Test batch relevance classification."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='[0.9, 0.5, 0.2]'))]
        mock_openai.chat.completions.create.return_value = mock_response
        
        config = Mock()
        config.openai_api_key = 'test_key'
        config.openai_model = 'gpt-4'
        config.topic = 'AI tools'
        
        candidates = [
            Mock(title='AI Tool 1', description='About AI', source_name='Tech'),
            Mock(title='Random Article', description='Not about AI', source_name='News'),
            Mock(title='Unrelated Topic', description='Sports', source_name='Sports')
        ]
        
        scores = classify_relevance_batch(candidates, 'AI tools', config)
        
        self.assertEqual(len(scores), 3)
        self.assertEqual(scores, [0.9, 0.5, 0.2])


class TestStore(unittest.TestCase):
    """Test DynamoDB storage operations."""
    
    def test_convert_floats_to_decimals(self):
        """Test float to Decimal conversion."""
        obj = {
            'score': 0.85,
            'embedding': [0.1, 0.2, 0.3],
            'nested': {'value': 1.5}
        }
        
        result = _convert_floats_to_decimals(obj)
        
        self.assertIsInstance(result['score'], Decimal)
        self.assertEqual(float(result['score']), 0.85)
        self.assertIsInstance(result['embedding'][0], Decimal)
        self.assertIsInstance(result['nested']['value'], Decimal)
    
    def test_convert_decimals_to_floats(self):
        """Test Decimal to float conversion."""
        obj = {
            'score': Decimal('0.85'),
            'embedding': [Decimal('0.1'), Decimal('0.2')],
            'nested': {'value': Decimal('1.5')}
        }
        
        result = _convert_decimals_to_floats(obj)
        
        self.assertIsInstance(result['score'], float)
        self.assertEqual(result['score'], 0.85)
        self.assertIsInstance(result['embedding'][0], float)
        self.assertIsInstance(result['nested']['value'], float)
    
    @patch('source_scout.store.dynamodb')
    def test_save_candidates(self, mock_dynamodb):
        """Test saving candidates to DynamoDB."""
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        candidates = [
            NewsCandidate(
                canonical_url='https://example.com/1',
                original_url='https://example.com/1',
                title='Test Article',
                description='Description',
                source_name='Test',
                source_domain='example.com',
                published_at='2024-01-01T00:00:00Z',
                fetched_at='2024-01-01T00:00:00Z',
                language='en',
                topic='test',
                relevance_score=0.8,
                quality_score=0.7,
                embedding=[0.1, 0.2],
                status='new'
            )
        ]
        
        save_candidates(candidates, 'test_table')
        
        self.assertTrue(mock_table.put_item.called)
    
    @patch('source_scout.store.dynamodb')
    def test_get_existing_urls(self, mock_dynamodb):
        """Test checking for existing URLs."""
        mock_dynamodb.batch_get_item.return_value = {
            'Responses': {
                'test_table': [
                    {'canonical_url': 'https://example.com/1', 'topic': 'test'}
                ]
            }
        }
        
        urls = ['https://example.com/1', 'https://example.com/2']
        existing = get_existing_urls(urls, 'test', 'test_table')
        
        self.assertIn('https://example.com/1', existing)
        self.assertNotIn('https://example.com/2', existing)


class TestFetcher(unittest.TestCase):
    """Test NewsAPI fetcher."""
    
    @patch('source_scout.fetcher.NewsApiClient')
    def test_fetch_news_success(self, mock_newsapi_class):
        """Test successful news fetching."""
        mock_client = Mock()
        mock_client.get_everything.return_value = {
            'status': 'ok',
            'articles': [
                {'title': 'Article 1', 'url': 'https://example.com/1'},
                {'title': 'Article 2', 'url': 'https://example.com/2'}
            ]
        }
        mock_newsapi_class.return_value = mock_client
        
        config = Mock()
        config.newsapi_api_key = 'test_key'
        config.topic = 'AI'
        config.time_window_hours = 24
        config.max_candidates = 20
        
        articles = fetch_news(config)
        
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]['title'], 'Article 1')
    
    @patch('source_scout.fetcher.NewsApiClient')
    @patch('source_scout.fetcher.time.sleep')
    def test_fetch_news_retry(self, mock_sleep, mock_newsapi_class):
        """Test retry logic on failure."""
        mock_client = Mock()
        mock_client.get_everything.side_effect = [
            Exception('API Error'),
            Exception('API Error'),
            {
                'status': 'ok',
                'articles': [{'title': 'Success', 'url': 'https://example.com'}]
            }
        ]
        mock_newsapi_class.return_value = mock_client
        
        config = Mock()
        config.newsapi_api_key = 'test_key'
        config.topic = 'AI'
        config.time_window_hours = 24
        config.max_candidates = 20
        
        articles = fetch_news(config)
        
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['title'], 'Success')
        self.assertEqual(mock_sleep.call_count, 2)  # Two retries


class TestScoutRunner(unittest.TestCase):
    """Test scout runner."""
    
    @patch('scout_runner.ScoutConfig')
    @patch('scout_runner.fetch_news')
    @patch('scout_runner.normalize_articles')
    @patch('scout_runner.deduplicate')
    @patch('scout_runner.filter_quality')
    @patch('scout_runner.save_candidates')
    def test_run_scout_success(self, mock_save, mock_filter, mock_dedup, 
                               mock_normalize, mock_fetch, mock_config_class):
        """Test successful scout runner execution."""
        from scout_runner import run_scout
        
        # Mock config
        mock_config = Mock()
        mock_config.topic = 'AI tools'
        mock_config.news_candidates_table = 'test_table'
        mock_config_class.from_env.return_value = mock_config
        
        # Mock pipeline steps
        mock_fetch.return_value = [{'title': 'Article 1'}]
        mock_normalize.return_value = [Mock()]
        mock_dedup.return_value = [Mock()]
        mock_filter.return_value = [Mock(), Mock()]
        
        # Execute runner
        result = run_scout()
        
        # Verify response
        self.assertTrue(result['success'])
        self.assertEqual(result['candidates_stored'], 2)
        
        # Verify all steps were called
        mock_fetch.assert_called_once()
        mock_normalize.assert_called_once()
        mock_dedup.assert_called_once()
        mock_filter.assert_called_once()
        mock_save.assert_called_once()


class TestMainHandlers(unittest.TestCase):
    """Test main Lambda handlers."""
    
    @patch('main.run_scout')
    @patch('main.generate_content_with_retry')
    @patch('main.post_to_x')
    @patch('main.build_prompt')
    @patch('main.load_prompt_template')
    def test_lambda_handler_success(self, mock_load_template, mock_build_prompt,
                                    mock_post, mock_generate, mock_run_scout):
        """Test successful lambda handler execution with scout."""
        from main import lambda_handler
        
        # Mock scout result
        mock_run_scout.return_value = {
            'success': True,
            'candidates_stored': 3,
            'message': 'Success'
        }
        
        # Mock other steps
        mock_load_template.return_value = 'template'
        mock_build_prompt.return_value = 'prompt'
        mock_generate.return_value = 'generated content'
        mock_post.return_value = 'post_123'
        
        # Execute handler
        event = {'id': 'test-event'}
        context = Mock()
        response = lambda_handler(event, context)
        
        # Verify response
        self.assertEqual(response['statusCode'], 200)
        self.assertIn('post_id', response['body'])
        
        # Verify all steps were called
        mock_run_scout.assert_called_once()
        mock_generate.assert_called_once()
        mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
