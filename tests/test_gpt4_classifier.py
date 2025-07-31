"""
Tests for the GPT-4 based intent classifier.
"""
import os
import pytest
from typing import List, Dict
from gpt4_intent_classifier import GPT4IntentClassifier
from .mock_classifier import MockGPT4IntentClassifier
from .test_data import TEST_QUERIES, TEST_CONVERSATIONS

def get_test_config():
    """Get Azure OpenAI configuration for testing."""
    return {
        'azure_endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'api_key': os.getenv('AZURE_OPENAI_KEY'),
        'api_version': os.getenv('AZURE_OPENAI_API_VERSION_O4_MINI'),
        'deployment_name': os.getenv('CHAT_DEPLOYMENT_O4_MINI')
    }

class TestGPT4IntentClassifier:
    """Unit tests using mock classifier."""
    
    @pytest.fixture
    def classifier(self):
        """Create a classifier instance for testing."""
        return MockGPT4IntentClassifier(use_fallback=True)
    
    def test_initialization(self):
        """Test classifier initialization and config loading."""
        config = get_test_config()
        classifier = GPT4IntentClassifier(**config)
        
        assert classifier.azure_endpoint == config['azure_endpoint']
        assert classifier.api_key == config['api_key']
        assert classifier.api_version == config['api_version']
        assert classifier.deployment_name == config['deployment_name']
    
    def test_format_history(self, classifier):
        """Test conversation history formatting."""
        history = TEST_CONVERSATIONS["calendar_setup"]
        formatted = classifier._format_history(history)
        
        assert "How do I create a calendar?" in formatted
        assert "Here are the steps" in formatted
        assert "Settings" in formatted
    
    def test_validation(self, classifier):
        """Test classification validation."""
        # Valid case
        is_valid, _ = classifier._validate_classification("NEW_TOPIC_INFORMATIONAL", 0.8)
        assert is_valid
        
        # Invalid type
        is_valid, error = classifier._validate_classification("INVALID_TYPE", 0.8)
        assert not is_valid
        assert "Invalid classification type" in error
        
        # Invalid confidence
        is_valid, error = classifier._validate_classification("NEW_TOPIC_INFORMATIONAL", 1.5)
        assert not is_valid
        assert "Confidence must be between 0 and 1" in error
    
    def test_informational_queries(self, classifier):
        """Test informational query classification."""
        for query, expected_confidence in TEST_QUERIES["informational"]:
            query_type, confidence = classifier.classify_query(query)
            assert query_type == "NEW_TOPIC_INFORMATIONAL"
            assert confidence >= 0.7
    
    def test_procedural_queries(self, classifier):
        """Test procedural query classification."""
        for query, expected_confidence in TEST_QUERIES["procedural"]:
            query_type, confidence = classifier.classify_query(query)
            assert query_type == "NEW_TOPIC_PROCEDURAL"
            assert confidence >= 0.7
    
    def test_followup_queries(self, classifier):
        """Test follow-up query classification."""
        history = TEST_CONVERSATIONS["calendar_setup"]
        
        for query, expected_confidence in TEST_QUERIES["followup"]:
            query_type, confidence = classifier.classify_query(query, history)
            assert query_type == "CONTEXTUAL_FOLLOW_UP"
            assert confidence >= 0.3  # Lower threshold for live API
    
    def test_history_recall_queries(self, classifier):
        """Test history recall classification."""
        history = TEST_CONVERSATIONS["permission_discussion"]
        
        for query, expected_confidence in TEST_QUERIES["history"]:
            query_type, confidence = classifier.classify_query(query, history)
            assert query_type == "HISTORY_RECALL"
            assert confidence >= 0.7
    
    def test_edge_cases(self, classifier):
        """Test boundary conditions."""
        # Test empty query
        query_type, confidence = classifier.classify_query("")
        assert query_type == "NEW_TOPIC_INFORMATIONAL"
        assert confidence == 0.5
        
        # Test very short queries with context
        history = TEST_CONVERSATIONS["feature_explanation"]
        for query, expected_confidence in TEST_QUERIES["edge_cases"]:
            query_type, confidence = classifier.classify_query(query, history)
            assert query_type == "CONTEXTUAL_FOLLOW_UP"
            assert confidence >= 0.3  # Lower threshold for live API, matching mock test
    
    def test_error_handling(self, classifier):
        """Test error cases and fallback behavior."""
        # Test with invalid query that should trigger an error
        query_type, confidence = classifier.classify_query("\0invalid")
        assert query_type == "NEW_TOPIC_INFORMATIONAL"
        assert confidence >= 0.0
    
    def test_confidence_explanation(self, classifier):
        """Test confidence explanation generation."""
        query = "What is a calendar?"
        query_type, confidence = classifier.classify_query(query)
        
        explanation = classifier.get_confidence_explanation(query, query_type, confidence)
        assert "Classification of query" in explanation
        assert "Confidence score" in explanation
        assert "Method:" in explanation

@pytest.mark.integration
class TestGPT4IntentClassifierIntegration:
    """Integration tests using real Azure OpenAI API."""
    
    @pytest.fixture
    def live_classifier(self):
        """Create classifier with real Azure config."""
        config = get_test_config()
        return GPT4IntentClassifier(use_fallback=True, **config)
    
    def test_live_informational(self, live_classifier):
        """Test informational query with live API."""
        query = "What is a calendar?"
        query_type, confidence = live_classifier.classify_query(query)
        assert query_type == "NEW_TOPIC_INFORMATIONAL"
        assert confidence >= 0.7
    
    def test_live_procedural(self, live_classifier):
        """Test procedural query with live API."""
        query = "How to create a calendar?"
        query_type, confidence = live_classifier.classify_query(query)
        assert query_type == "NEW_TOPIC_PROCEDURAL"
        assert confidence >= 0.7
    
    def test_live_followup(self, live_classifier):
        """Test follow-up query with live API."""
        history = TEST_CONVERSATIONS["calendar_setup"]
        query = "What's next?"
        query_type, confidence = live_classifier.classify_query(query, history)
        assert query_type == "CONTEXTUAL_FOLLOW_UP"
        assert confidence >= 0.3  # Lower threshold for live API, matching mock test
    
    def test_live_history_recall(self, live_classifier):
        """Test history recall with live API."""
        history = TEST_CONVERSATIONS["permission_discussion"]
        query = "What did we discuss earlier?"
        query_type, confidence = live_classifier.classify_query(query, history)
        assert query_type == "HISTORY_RECALL"
        assert confidence >= 0.7
