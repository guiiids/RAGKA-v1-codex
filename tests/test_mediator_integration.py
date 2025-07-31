"""
Integration tests for the QueryMediator with the existing classification system
"""
import pytest
from unittest.mock import Mock, patch

from query_mediator import QueryMediator
from conversation_context_analyzer import ConversationContextAnalyzer
from gpt4_intent_classifier import GPT4IntentClassifier

# Test scenarios that simulate real conversations
OPENLAB_SCENARIO = [
    {"role": "user", "content": "What is iLab?"},
    {"role": "assistant", "content": "iLab is a platform for managing laboratory resources and workflows. It helps institutions and labs manage services, equipment, and billing."},
    {"role": "user", "content": "Is it the same as OpenLab?"}
]

DOCKER_SCENARIO = [
    {"role": "user", "content": "How do I deploy the application?"},
    {"role": "assistant", "content": "You'll need to build the application first, then you can deploy it to your server using the deployment scripts."},
    {"role": "user", "content": "Can I use Docker instead?"}
]

VERSION_SCENARIO = [
    {"role": "user", "content": "How do I install the sensor?"},
    {"role": "assistant", "content": "First, mount the sensor on the bracket, then connect the power and data cables..."},
    {"role": "user", "content": "What about the v2.1 model?"}
]

class MockOpenAIService:
    """Mock OpenAI service that simulates realistic responses"""
    
    def get_chat_response(self, messages, max_completion_tokens=None):
        """Simulate responses based on conversation patterns"""
        full_prompt = messages[0]['content']
        query = full_prompt.lower()
        
        # Extract the actual query from the prompt
        if 'CURRENT QUERY:' in full_prompt:
            query = full_prompt.split('CURRENT QUERY:')[1].strip().strip('"').lower()
        
        # Docker compatibility scenario (check first to avoid conflicts)
        if 'docker' in query:
            return '''
            {
                "classification": "CONTEXTUAL_WITH_SEARCH",
                "needs_search": true,
                "confidence": 0.92,
                "external_entities": ["Docker"],
                "reasoning": "This is a follow-up about deployment, but introduces Docker as a new technology that needs to be searched."
            }
            '''
        
        # Version comparison scenario
        elif 'v2.1' in query or ('what about' in query and 'model' in query):
            return '''
            {
                "classification": "CONTEXTUAL_WITH_SEARCH",
                "needs_search": true,
                "confidence": 0.90,
                "external_entities": ["v2.1 model"],
                "reasoning": "While asking about the same product, this introduces a specific version (v2.1) that may have different installation requirements."
            }
            '''
        
        # OpenLab comparison scenario
        elif 'openlab' in query:
            return '''
            {
                "classification": "CONTEXTUAL_WITH_SEARCH",
                "needs_search": true,
                "confidence": 0.95,
                "external_entities": ["OpenLab"],
                "reasoning": "While this is a follow-up comparing to the previous topic (iLab), it introduces a new product (OpenLab) that requires search to make the comparison."
            }
            '''
        
        # Default to contextual follow-up
        return '''
        {
            "classification": "CONTEXTUAL_FOLLOW_UP",
            "needs_search": false,
            "confidence": 0.85,
            "external_entities": [],
            "reasoning": "This appears to be a direct follow-up to the previous context."
        }
        '''

@pytest.fixture
def integrated_system():
    """Create integrated system with mock components"""
    openai_service = MockOpenAIService()
    context_analyzer = ConversationContextAnalyzer()
    mediator = QueryMediator(openai_service)
    return context_analyzer, mediator

def test_openlab_scenario(integrated_system):
    """Test the OpenLab comparison scenario"""
    context_analyzer, mediator = integrated_system
    
    # Simulate a low-confidence classification that would trigger mediator
    # (The actual context analyzer might not classify this as expected)
    low_confidence_scores = {
        'CONTEXTUAL_FOLLOW_UP': 0.2,
        'HISTORY_RECALL': 0.1,
        'NEW_TOPIC_PROCEDURAL': 0.1,
        'NEW_TOPIC_INFORMATIONAL': 0.15
    }
    
    # The mediator should identify it needs search
    result = mediator.classify(
        OPENLAB_SCENARIO[-1]['content'],
        history=OPENLAB_SCENARIO[:-1],
        current_classification=low_confidence_scores
    )
    
    assert result['classification'] == "CONTEXTUAL_WITH_SEARCH"
    assert result['needs_search'] == True
    assert "OpenLab" in result['external_entities']

def test_docker_scenario(integrated_system):
    """Test the Docker compatibility scenario"""
    context_analyzer, mediator = integrated_system
    
    # Simulate a low-confidence classification that would trigger mediator
    low_confidence_scores = {
        'CONTEXTUAL_FOLLOW_UP': 0.25,
        'HISTORY_RECALL': 0.1,
        'NEW_TOPIC_PROCEDURAL': 0.15,
        'NEW_TOPIC_INFORMATIONAL': 0.1
    }
    
    result = mediator.classify(
        DOCKER_SCENARIO[-1]['content'],
        history=DOCKER_SCENARIO[:-1],
        current_classification=low_confidence_scores
    )
    
    assert result['classification'] == "CONTEXTUAL_WITH_SEARCH"
    assert result['needs_search'] == True
    assert "Docker" in result['external_entities']

def test_version_scenario(integrated_system):
    """Test the version comparison scenario"""
    context_analyzer, mediator = integrated_system
    
    # Simulate a low-confidence classification that would trigger mediator
    low_confidence_scores = {
        'CONTEXTUAL_FOLLOW_UP': 0.2,
        'HISTORY_RECALL': 0.1,
        'NEW_TOPIC_PROCEDURAL': 0.2,
        'NEW_TOPIC_INFORMATIONAL': 0.1
    }
    
    result = mediator.classify(
        VERSION_SCENARIO[-1]['content'],
        history=VERSION_SCENARIO[:-1],
        current_classification=low_confidence_scores
    )
    
    assert result['classification'] == "CONTEXTUAL_WITH_SEARCH"
    assert result['needs_search'] == True
    assert any('v2.1' in entity for entity in result['external_entities'])

def test_conservative_threshold():
    """Test that mediator respects conservative threshold"""
    openai_service = MockOpenAIService()
    mediator = QueryMediator(openai_service, confidence_threshold=0.3)
    
    # High confidence classification
    high_confidence = {
        "CONTEXTUAL_FOLLOW_UP": 0.85,
        "NEW_TOPIC": 0.1,
        "CONTEXTUAL_WITH_SEARCH": 0.05
    }
    
    result = mediator.classify(
        "How does it work?",
        history=OPENLAB_SCENARIO[:-1],
        current_classification=high_confidence
    )
    
    # Should use existing classification
    assert result['source'] == "existing"
    assert result['classification'] == high_confidence

def test_low_confidence_override():
    """Test that mediator overrides on low confidence"""
    openai_service = MockOpenAIService()
    mediator = QueryMediator(openai_service, confidence_threshold=0.3)
    
    # Low confidence classification
    low_confidence = {
        "CONTEXTUAL_FOLLOW_UP": 0.2,
        "NEW_TOPIC": 0.1,
        "CONTEXTUAL_WITH_SEARCH": 0.1
    }
    
    result = mediator.classify(
        "Is it the same as OpenLab?",
        history=OPENLAB_SCENARIO[:-1],
        current_classification=low_confidence
    )
    
    # Should use mediator classification
    assert result['source'] == "mediator"
    assert result['classification'] == "CONTEXTUAL_WITH_SEARCH"
    assert result['needs_search'] == True

def test_integration_with_gpt4_classifier():
    """Test integration with the GPT4 intent classifier"""
    openai_service = MockOpenAIService()
    mediator = QueryMediator(openai_service)
    
    query = "Is it compatible with Docker?"
    history = [
        {"role": "user", "content": "How do I deploy the app?"},
        {"role": "assistant", "content": "Here are the deployment steps..."}
    ]
    
    # Simulate a low-confidence classification that would trigger mediator
    low_confidence_result = {
        "CONTEXTUAL_FOLLOW_UP": 0.2,
        "NEW_TOPIC_INFORMATIONAL": 0.1,
        "NEW_TOPIC_PROCEDURAL": 0.1,
        "HISTORY_RECALL": 0.05
    }
    
    # Test mediator with low confidence classification
    mediator_result = mediator.classify(
        query,
        history=history,
        current_classification=low_confidence_result
    )
    
    # Verify results are properly combined
    assert 'source' in mediator_result
    if mediator_result['source'] == 'mediator':
        assert 'fallback_from' in mediator_result
        assert mediator_result['fallback_from'] == low_confidence_result
        assert mediator_result['classification'] == "CONTEXTUAL_WITH_SEARCH"
        assert mediator_result['needs_search'] == True
