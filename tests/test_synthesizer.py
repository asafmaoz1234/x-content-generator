"""
Tests for synthesizer module.
"""
import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from synthesizer import (
    SourceFact,
    SynthesisResult,
    fetch_unused_candidates,
    synthesize_angle,
    validate_grounding,
    _convert_decimals_to_floats
)
from source_scout.normalizer import NewsCandidate
from source_scout.config import ScoutConfig
from decimal import Decimal


class TestSourceFact(unittest.TestCase):
    """Tests for SourceFact dataclass."""
    
    def test_to_dict(self):
        """Test converting SourceFact to dictionary."""
        fact = SourceFact(
            fact="OpenAI released GPT-5",
            source_url="https://example.com/article",
            source_name="TechCrunch"
        )
        
        result = fact.to_dict()
        
        self.assertEqual(result['fact'], "OpenAI released GPT-5")
        self.assertEqual(result['source_url'], "https://example.com/article")
        self.assertEqual(result['source_name'], "TechCrunch")
    
    def test_from_dict(self):
        """Test creating SourceFact from dictionary."""
        data = {
            'fact': "OpenAI released GPT-5",
            'source_url': "https://example.com/article",
            'source_name': "TechCrunch"
        }
        
        fact = SourceFact.from_dict(data)
        
        self.assertEqual(fact.fact, "OpenAI released GPT-5")
        self.assertEqual(fact.source_url, "https://example.com/article")
        self.assertEqual(fact.source_name, "TechCrunch")


class TestSynthesisResult(unittest.TestCase):
    """Tests for SynthesisResult dataclass."""
    
    def test_to_dict(self):
        """Test converting SynthesisResult to dictionary."""
        facts = [
            SourceFact("Fact 1", "url1", "Source 1"),
            SourceFact("Fact 2", "url2", "Source 2")
        ]
        
        result = SynthesisResult(
            angle="AI tools are revolutionizing productivity",
            hook="The future is here:",
            key_facts=facts,
            draft_post="Check out these amazing AI tools!",
            source_candidates_used=["url1", "url2"]
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict['angle'], "AI tools are revolutionizing productivity")
        self.assertEqual(result_dict['hook'], "The future is here:")
        self.assertEqual(len(result_dict['key_facts']), 2)
        self.assertEqual(result_dict['draft_post'], "Check out these amazing AI tools!")
        self.assertEqual(len(result_dict['source_candidates_used']), 2)
    
    def test_from_dict(self):
        """Test creating SynthesisResult from dictionary."""
        data = {
            'angle': "Test angle",
            'hook': "Test hook",
            'key_facts': [
                {'fact': "Fact 1", 'source_url': "url1", 'source_name': "Source 1"}
            ],
            'draft_post': "Test post",
            'source_candidates_used': ["url1"]
        }
        
        result = SynthesisResult.from_dict(data)
        
        self.assertEqual(result.angle, "Test angle")
        self.assertEqual(result.hook, "Test hook")
        self.assertEqual(len(result.key_facts), 1)
        self.assertEqual(result.draft_post, "Test post")
        self.assertEqual(len(result.source_candidates_used), 1)


class TestConvertDecimals(unittest.TestCase):
    """Tests for decimal conversion utility."""
    
    def test_convert_decimals_to_floats_scalar(self):
        """Test converting a single Decimal to float."""
        decimal_val = Decimal('0.95')
        result = _convert_decimals_to_floats(decimal_val)
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 0.95)
    
    def test_convert_decimals_to_floats_dict(self):
        """Test converting Decimals in a dictionary."""
        data = {
            'score': Decimal('0.85'),
            'name': 'Test',
            'nested': {
                'value': Decimal('0.95')
            }
        }
        
        result = _convert_decimals_to_floats(data)
        
        self.assertIsInstance(result['score'], float)
        self.assertAlmostEqual(result['score'], 0.85)
        self.assertEqual(result['name'], 'Test')
        self.assertIsInstance(result['nested']['value'], float)
    
    def test_convert_decimals_to_floats_list(self):
        """Test converting Decimals in a list."""
        data = [Decimal('0.5'), Decimal('0.75'), 'string', 100]
        
        result = _convert_decimals_to_floats(data)
        
        self.assertIsInstance(result[0], float)
        self.assertIsInstance(result[1], float)
        self.assertEqual(result[2], 'string')
        self.assertEqual(result[3], 100)


class TestValidateGrounding(unittest.TestCase):
    """Tests for grounding validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.candidates = [
            NewsCandidate(
                canonical_url="https://example.com/article1",
                original_url="https://example.com/article1",
                title="Test Article 1",
                description="Description 1",
                source_name="TechCrunch",
                source_domain="techcrunch.com",
                published_at=datetime.utcnow().isoformat(),
                fetched_at=datetime.utcnow().isoformat(),
                language="en",
                topic="AI",
                quality_score=0.9
            ),
            NewsCandidate(
                canonical_url="https://example.com/article2",
                original_url="https://example.com/article2",
                title="Test Article 2",
                description="Description 2",
                source_name="Reuters",
                source_domain="reuters.com",
                published_at=datetime.utcnow().isoformat(),
                fetched_at=datetime.utcnow().isoformat(),
                language="en",
                topic="AI",
                quality_score=0.85
            )
        ]
    
    def test_validate_grounding_success(self):
        """Test validation passes with properly grounded facts."""
        facts = [
            SourceFact("Fact 1", "https://example.com/article1", "TechCrunch"),
            SourceFact("Fact 2", "https://example.com/article2", "Reuters")
        ]
        
        result = SynthesisResult(
            angle="Test angle",
            hook="Test hook",
            key_facts=facts,
            draft_post="Test post",
            source_candidates_used=["https://example.com/article1", "https://example.com/article2"]
        )
        
        is_valid = validate_grounding(result, self.candidates)
        
        self.assertTrue(is_valid)
    
    def test_validate_grounding_invalid_fact_url(self):
        """Test validation fails with invalid fact URL."""
        facts = [
            SourceFact("Fact 1", "https://example.com/article1", "TechCrunch"),
            SourceFact("Fake fact", "https://fake.com/article", "FakeSource")
        ]
        
        result = SynthesisResult(
            angle="Test angle",
            hook="Test hook",
            key_facts=facts,
            draft_post="Test post",
            source_candidates_used=["https://example.com/article1"]
        )
        
        is_valid = validate_grounding(result, self.candidates)
        
        self.assertFalse(is_valid)
    
    def test_validate_grounding_invalid_source_candidate(self):
        """Test validation fails with invalid source candidate URL."""
        facts = [
            SourceFact("Fact 1", "https://example.com/article1", "TechCrunch")
        ]
        
        result = SynthesisResult(
            angle="Test angle",
            hook="Test hook",
            key_facts=facts,
            draft_post="Test post",
            source_candidates_used=["https://example.com/article1", "https://invalid.com/article"]
        )
        
        is_valid = validate_grounding(result, self.candidates)
        
        self.assertFalse(is_valid)
    
    def test_validate_grounding_empty_facts(self):
        """Test validation passes with no facts (edge case)."""
        result = SynthesisResult(
            angle="Test angle",
            hook="Test hook",
            key_facts=[],
            draft_post="Test post",
            source_candidates_used=[]
        )
        
        is_valid = validate_grounding(result, self.candidates)
        
        self.assertTrue(is_valid)


class TestFetchUnusedCandidates(unittest.TestCase):
    """Tests for fetching unused candidates from DynamoDB."""
    
    @patch('synthesizer.dynamodb')
    def test_fetch_unused_candidates_success(self, mock_dynamodb):
        """Test successfully fetching unused candidates."""
        # Mock config
        config = Mock(spec=ScoutConfig)
        config.topic = "AI"
        config.news_candidates_table = "test-table"
        
        # Mock DynamoDB response
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        mock_table.query.return_value = {
            'Items': [
                {
                    'canonical_url': 'https://example.com/article1',
                    'original_url': 'https://example.com/article1',
                    'title': 'Test Article 1',
                    'description': 'Description 1',
                    'source_name': 'TechCrunch',
                    'source_domain': 'techcrunch.com',
                    'published_at': datetime.utcnow().isoformat(),
                    'fetched_at': datetime.utcnow().isoformat(),
                    'language': 'en',
                    'topic': 'AI',
                    'status': 'new',
                    'quality_score': Decimal('0.9'),
                    'relevance_score': Decimal('0.85'),
                    'embedding': []
                }
            ]
        }
        
        candidates = fetch_unused_candidates(config, days=7, max_candidates=20)
        
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, 'Test Article 1')
        self.assertEqual(candidates[0].status, 'new')
        self.assertIsInstance(candidates[0].quality_score, float)
    
    @patch('synthesizer.dynamodb')
    def test_fetch_unused_candidates_filters_used(self, mock_dynamodb):
        """Test that used candidates are filtered out."""
        config = Mock(spec=ScoutConfig)
        config.topic = "AI"
        config.news_candidates_table = "test-table"
        
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        mock_table.query.return_value = {
            'Items': [
                {
                    'canonical_url': 'https://example.com/article1',
                    'original_url': 'https://example.com/article1',
                    'title': 'Used Article',
                    'description': 'Description',
                    'source_name': 'TechCrunch',
                    'source_domain': 'techcrunch.com',
                    'published_at': datetime.utcnow().isoformat(),
                    'fetched_at': datetime.utcnow().isoformat(),
                    'language': 'en',
                    'topic': 'AI',
                    'status': 'used',  # This should be filtered out
                    'quality_score': Decimal('0.9'),
                    'relevance_score': Decimal('0.85'),
                    'embedding': []
                }
            ]
        }
        
        candidates = fetch_unused_candidates(config, days=7, max_candidates=20)
        
        self.assertEqual(len(candidates), 0)
    
    @patch('synthesizer.dynamodb')
    def test_fetch_unused_candidates_respects_max_limit(self, mock_dynamodb):
        """Test that max_candidates limit is respected."""
        config = Mock(spec=ScoutConfig)
        config.topic = "AI"
        config.news_candidates_table = "test-table"
        
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Create 10 mock items
        items = []
        for i in range(10):
            items.append({
                'canonical_url': f'https://example.com/article{i}',
                'original_url': f'https://example.com/article{i}',
                'title': f'Test Article {i}',
                'description': f'Description {i}',
                'source_name': 'TechCrunch',
                'source_domain': 'techcrunch.com',
                'published_at': datetime.utcnow().isoformat(),
                'fetched_at': datetime.utcnow().isoformat(),
                'language': 'en',
                'topic': 'AI',
                'status': 'new',
                'quality_score': Decimal('0.9'),
                'relevance_score': Decimal('0.85'),
                'embedding': []
            })
        
        mock_table.query.return_value = {'Items': items}
        
        candidates = fetch_unused_candidates(config, days=7, max_candidates=5)
        
        self.assertEqual(len(candidates), 5)


class TestSynthesizeAngle(unittest.TestCase):
    """Tests for angle synthesis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.candidates = [
            NewsCandidate(
                canonical_url="https://example.com/article1",
                original_url="https://example.com/article1",
                title="AI Tool Launches New Feature",
                description="Description of the feature",
                source_name="TechCrunch",
                source_domain="techcrunch.com",
                published_at=datetime.utcnow().isoformat(),
                fetched_at=datetime.utcnow().isoformat(),
                language="en",
                topic="AI",
                quality_score=0.9
            )
        ]
        
        self.config = Mock(spec=ScoutConfig)
        self.config.topic = "AI"
        self.config.openai_api_key = "test-key"
        self.config.openai_model = "gpt-4"
    
    def test_synthesize_angle_no_candidates(self):
        """Test synthesis with no candidates returns None."""
        result = synthesize_angle([], self.config)
        self.assertIsNone(result)
    
    @patch('synthesizer.openai.chat.completions.create')
    @patch('builtins.open', create=True)
    def test_synthesize_angle_success(self, mock_open, mock_openai_create):
        """Test successful angle synthesis."""
        # Mock prompt template
        mock_open.return_value.__enter__.return_value.read.return_value = """
Topic: {topic}
Candidates: {candidates}
Count: {num_candidates}
"""
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """{
            "angle": "Test angle",
            "hook": "Test hook",
            "key_facts": [
                {
                    "fact": "Fact 1",
                    "source_url": "https://example.com/article1",
                    "source_name": "TechCrunch"
                }
            ],
            "draft_post": "Test post",
            "source_urls": ["https://example.com/article1"]
        }"""
        mock_openai_create.return_value = mock_response
        
        result = synthesize_angle(self.candidates, self.config)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.angle, "Test angle")
        self.assertEqual(result.hook, "Test hook")
        self.assertEqual(len(result.key_facts), 1)
        self.assertEqual(result.draft_post, "Test post")
        self.assertEqual(len(result.source_candidates_used), 1)
    
    @patch('synthesizer.openai.chat.completions.create')
    @patch('builtins.open', create=True)
    def test_synthesize_angle_invalid_json(self, mock_open, mock_openai_create):
        """Test synthesis with invalid JSON response."""
        mock_open.return_value.__enter__.return_value.read.return_value = "template"
        
        # Mock OpenAI response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Not valid JSON"
        mock_openai_create.return_value = mock_response
        
        result = synthesize_angle(self.candidates, self.config)
        
        self.assertIsNone(result)
    
    @patch('builtins.open', create=True)
    def test_synthesize_angle_missing_template(self, mock_open):
        """Test synthesis when template file is missing."""
        mock_open.side_effect = FileNotFoundError()
        
        result = synthesize_angle(self.candidates, self.config)
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
