"""
Tests for the GPT-4 based intent classifier.
"""
import os
import pytest
from typing import List, Dict
from gpt4_intent_classifier import GPT4IntentClassifier

def get_test_config():
    """Get Azure OpenAI configuration for testing."""
    return {
        'azure_endpoint': os.getenv('AZURE_OPENAI_ENDPOINT'),
        'api_key': os.getenv('AZURE_OPENAI_KEY'),
        'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT')
    }

@pytest.fixture
def classifier():
    """Create a classifier instance for testing."""
    config = get_test_config()
    return GPT4IntentClassifier(use_fallback=True, **config)

def test_basic_classification():
    """Test basic query classification."""
    config = get_test_config()
    classifier = GPT4IntentClassifier(use_fallback=False, **config)
    
    # Test informational queries
    informational_queries = [
        "What is a calendar?",
        "Tell me about user permissions",
        "When was this feature added?",
        "Why do we need this?"
    ]
    
    for query in informational_queries:
        query_type, confidence = classifier.classify_query(query)
        assert query_type == "NEW_TOPIC_INFORMATIONAL"
        assert confidence >= 0.7
    
    # Test procedural queries
    procedural_queries = [
        "How to create a calendar?",
        "What are the steps to configure permissions?",
        "Guide me through the setup process",
        "Show me how to add users"
    ]
    
    for query in procedural_queries:
        query_type, confidence = classifier.classify_query(query)
        assert query_type == "NEW_TOPIC_PROCEDURAL"
        assert confidence >= 0.7

def test_context_awareness():
    """Test classification with conversation context."""
    config = get_test_config()
    classifier = GPT4IntentClassifier(use_fallback=False, **config)
    
    # Create conversation history
    history = [
        {"role": "user", "content": "How do I create a calendar?"},
        {"role": "assistant", "content": "Here are the steps:\n1. Go to Settings\n2. Click 'Add Calendar'"}
    ]
    
    # Test follow-up queries
    follow_up_queries = [
        "What's next?",
        "Tell me more about that",
        "Can you elaborate?",
        "What about step 2?"
    ]
    
    for query in follow_up_queries:
        query_type, confidence = classifier.classify_query(query, history)
        assert query_type == "CONTEXTUAL_FOLLOW_UP"
        assert confidence >= 0.6

def test_history_recall():
    """Test history recall detection."""
    config = get_test_config()
    classifier = GPT4IntentClassifier(use_fallback=False, **config)
    
    # Create longer conversation history
    history = [
        {"role": "user", "content": "How do I create a calendar?"},
        {"role": "assistant", "content": "Here are the steps..."},
        {"role": "user", "content": "What about sharing it?"},
        {"role": "assistant", "content": "You can share by..."}
    ]
    
    # Test history recall queries
    recall_queries = [
        "What was my first question?",
        "What did we discuss earlier?",
        "Can you summarize our conversation?",
        "What did you tell me about creating calendars?"
    ]
    
    for query in recall_queries:
        query_type, confidence = classifier.classify_query(query, history)
        assert query_type == "HISTORY_RECALL"
        assert confidence >= 0.7

def test_edge_cases():
    """Test edge cases and boundary conditions."""
    config = get_test_config()
    classifier = GPT4IntentClassifier(use_fallback=False, **config)
    
    # Test empty query
    query_type, confidence = classifier.classify_query("")
    assert query_type == "NEW_TOPIC_INFORMATIONAL"
    assert confidence == 0.5
    
    # Test very short queries with context
    history = [
        {"role": "user", "content": "What is a calendar?"},
        {"role": "assistant", "content": "A calendar is a system for organizing days..."}
    ]
    
    short_queries = ["?", "help", "next"]
    for query in short_queries:
        query_type, confidence = classifier.classify_query(query, history)
        assert query_type == "CONTEXTUAL_FOLLOW_UP"
        assert confidence >= 0.6

def test_fallback_behavior():
    """Test fallback to regex classifier."""
    config = get_test_config()
    classifier = GPT4IntentClassifier(use_fallback=True, **config)
    
    # Simulate OpenAI API failure by using an invalid query that would trigger an exception
    query_type, confidence = classifier.classify_query("\0invalid")  # Null byte should trigger an error
    
    # Should fall back to regex classifier
    assert query_type in ["NEW_TOPIC_INFORMATIONAL", "NEW_TOPIC_PROCEDURAL"]
    assert confidence >= 0.0

def test_confidence_explanation():
    """Test confidence explanation generation."""
    config = get_test_config()
    classifier = GPT4IntentClassifier(use_fallback=False, **config)
    
    query = "What is a calendar?"
    query_type, confidence = classifier.classify_query(query)
    
    explanation = classifier.get_confidence_explanation(query, query_type, confidence)
    assert "Classification of query" in explanation
    assert "Confidence score" in explanation
    assert "Method: GPT-4" in explanation
