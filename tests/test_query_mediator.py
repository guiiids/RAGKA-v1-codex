"""
Unit tests for the QueryMediator class
"""
import json
import pytest
from unittest.mock import Mock, patch

from query_mediator import QueryMediator

# Sample test data
SAMPLE_HISTORY = [
    {"role": "user", "content": "What is iLab?"},
    {"role": "assistant", "content": "iLab is a platform for managing laboratory resources and workflows."},
]

SAMPLE_CLASSIFICATIONS = {
    "CONTEXTUAL_FOLLOW_UP": 0.2,
    "NEW_TOPIC": 0.1,
    "CONTEXTUAL_WITH_SEARCH": 0.1
}

class MockOpenAIService:
    """Mock OpenAI service for testing"""
    def get_chat_response(self, messages, max_completion_tokens=None):
        """Mock response based on query content"""
        query = messages[0]['content']
        
        if "error" in query.lower():
            raise Exception("Simulated API error")
            
        if "invalid_json" in query.lower():
            return "Invalid JSON response"
            
        # Default mock response
        return json.dumps({
            "classification": "CONTEXTUAL_WITH_SEARCH",
            "needs_search": True,
            "confidence": 0.9,
            "external_entities": ["OpenLab"],
            "reasoning": "Test reasoning"
        })

@pytest.fixture
def mediator():
    """Create a mediator instance with mock OpenAI service"""
    openai_service = MockOpenAIService()
    return QueryMediator(openai_service)

def test_should_mediate_low_confidence(mediator):
    """Test that mediator activates on low confidence"""
    assert mediator.should_mediate(SAMPLE_CLASSIFICATIONS) == True

def test_should_mediate_high_confidence(mediator):
    """Test that mediator doesn't activate on high confidence"""
    classifications = {
        "CONTEXTUAL_FOLLOW_UP": 0.8,
        "NEW_TOPIC": 0.1
    }
    assert mediator.should_mediate(classifications) == False

def test_should_mediate_empty_classification(mediator):
    """Test that mediator activates on empty classification"""
    assert mediator.should_mediate({}) == True

def test_format_recent_context(mediator):
    """Test conversation history formatting"""
    context = mediator._format_recent_context(SAMPLE_HISTORY)
    assert "What is iLab?" in context
    assert "iLab is a platform" in context

def test_format_recent_context_empty(mediator):
    """Test formatting with empty history"""
    context = mediator._format_recent_context([])
    assert context == "[No previous conversation]"

def test_parse_response_valid(mediator):
    """Test parsing valid LLM response"""
    valid_response = json.dumps({
        "classification": "CONTEXTUAL_WITH_SEARCH",
        "needs_search": True,
        "confidence": 0.9,
        "reasoning": "Test reasoning"
    })
    result = mediator._parse_response(valid_response)
    assert result["classification"] == "CONTEXTUAL_WITH_SEARCH"
    assert result["needs_search"] == True
    assert "external_entities" in result

def test_parse_response_invalid_json(mediator):
    """Test handling invalid JSON response"""
    result = mediator._parse_response("Invalid JSON")
    assert result["classification"] == "NEW_TOPIC"
    assert result["error"] == True

def test_parse_response_missing_fields(mediator):
    """Test handling response with missing required fields"""
    invalid_response = json.dumps({
        "classification": "CONTEXTUAL_FOLLOW_UP"
        # Missing required fields
    })
    result = mediator._parse_response(invalid_response)
    assert result["error"] == True

def test_classify_basic(mediator):
    """Test basic classification flow"""
    result = mediator.classify(
        "Is it the same as OpenLab?",
        history=SAMPLE_HISTORY,
        current_classification=SAMPLE_CLASSIFICATIONS
    )
    assert result["source"] == "mediator"
    assert "classification" in result
    assert "confidence" in result

def test_classify_high_existing_confidence(mediator):
    """Test that high existing confidence skips mediation"""
    high_confidence = {
        "CONTEXTUAL_FOLLOW_UP": 0.9,
        "NEW_TOPIC": 0.1
    }
    result = mediator.classify(
        "How do I use it?",
        history=SAMPLE_HISTORY,
        current_classification=high_confidence
    )
    assert result["source"] == "existing"
    assert result["classification"] == high_confidence

def test_classify_api_error(mediator):
    """Test handling of API errors"""
    result = mediator.classify(
        "trigger error test",
        history=SAMPLE_HISTORY,
        current_classification=SAMPLE_CLASSIFICATIONS
    )
    assert result["source"] == "error"
    assert "error" in result

def test_classify_no_history(mediator):
    """Test classification without conversation history"""
    result = mediator.classify("What is OpenLab?")
    assert result["source"] == "mediator"
    assert "classification" in result

def test_classify_no_current_classification(mediator):
    """Test classification without current classification scores"""
    result = mediator.classify(
        "Is it compatible with Docker?",
        history=SAMPLE_HISTORY
    )
    assert result["source"] == "mediator"
    assert "classification" in result

def test_build_classification_prompt(mediator):
    """Test prompt building"""
    prompt = mediator._build_classification_prompt(
        "Is it the same as OpenLab?",
        SAMPLE_HISTORY
    )
    assert "CONVERSATION CONTEXT:" in prompt
    assert "CURRENT QUERY:" in prompt
    assert "Is it the same as OpenLab?" in prompt
    assert "What is iLab?" in prompt
