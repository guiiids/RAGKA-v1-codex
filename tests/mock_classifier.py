"""
Mock GPT-4 intent classifier for testing.
"""
from typing import Dict, List, Tuple, Optional
from gpt4_intent_classifier import GPT4IntentClassifier
from .test_data import MOCK_RESPONSES, TEST_QUERIES

class MockGPT4IntentClassifier(GPT4IntentClassifier):
    """Test double with predefined responses."""
    
    def __init__(self, use_fallback: bool = True):
        """Initialize with mock responses."""
        # Skip parent initialization to avoid API setup
        self.use_fallback = use_fallback
        self.mock_responses = MOCK_RESPONSES
        
        # Valid classification types (copied from parent)
        self.valid_types = {
            'NEW_TOPIC_INFORMATIONAL',
            'NEW_TOPIC_PROCEDURAL',
            'CONTEXTUAL_FOLLOW_UP',
            'HISTORY_RECALL'
        }
    
    def classify_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Tuple[str, float]:
        """Return mock responses for predictable testing."""
        # Handle empty query
        if not query:
            return "NEW_TOPIC_INFORMATIONAL", 0.5
            
        # Check for exact matches in mock responses
        if query in self.mock_responses:
            return self.mock_responses[query]
            
        # Check test queries
        query_lower = query.lower()
        
        # Informational queries
        if any(test_query.lower() == query_lower for test_query, _ in TEST_QUERIES["informational"]):
            return "NEW_TOPIC_INFORMATIONAL", 0.9
            
        # Procedural queries
        if any(test_query.lower() == query_lower for test_query, _ in TEST_QUERIES["procedural"]):
            return "NEW_TOPIC_PROCEDURAL", 0.9
            
        # History recall queries
        if any(test_query.lower() == query_lower for test_query, _ in TEST_QUERIES["history"]):
            return "HISTORY_RECALL", 0.9
            
        # Follow-up queries
        if conversation_history and any(test_query.lower() == query_lower for test_query, _ in TEST_QUERIES["followup"]):
            return "CONTEXTUAL_FOLLOW_UP", 0.8
            
        # Edge cases
        if conversation_history and any(test_query.lower() == query_lower for test_query, _ in TEST_QUERIES["edge_cases"]):
            return "CONTEXTUAL_FOLLOW_UP", 0.6
            
        # Default response
        return "NEW_TOPIC_INFORMATIONAL", 0.5
    
    def get_confidence_explanation(
        self,
        query: str,
        query_type: str,
        confidence: float
    ) -> str:
        """Get mock explanation."""
        explanation = [
            f"Classification of query: '{query}'",
            f"Detected type: {query_type}",
            f"Confidence score: {confidence:.2f}",
            "Method: Mock GPT-4 classifier"
        ]
        
        return "\n".join(explanation)
