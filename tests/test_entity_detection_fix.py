#!/usr/bin/env python3
"""
Test script to verify the entity detection fix for the memory failure.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from query_mediator import QueryMediator
from openai_service import OpenAIService

def test_openlab_detection():
    """Test that OpenLab is detected as a new entity requiring search."""
    print("Testing OpenLab entity detection...")
    
    # Mock OpenAI service for testing
    class MockOpenAIService:
        def get_chat_response(self, messages, max_completion_tokens=200):
            return '{"classification": "CONTEXTUAL_WITH_SEARCH", "needs_search": true, "confidence": 0.8, "external_entities": ["OpenLab"], "reasoning": "Detected new entity OpenLab not in conversation context"}'
    
    # Initialize mediator with enhanced settings
    mock_service = MockOpenAIService()
    mediator = QueryMediator(mock_service, confidence_threshold=0.6)
    
    # Test conversation history (about iLab)
    history = [
        {"role": "user", "content": "What is iLab?"},
        {"role": "assistant", "content": "iLab is a comprehensive platform for research institutions that provides service delivery, billing management, and facility management."}
    ]
    
    # Test query that introduces OpenLab
    query = "Is it the same as OpenLab?"
    
    # Test entity extraction
    has_new_entities, new_entities = mediator._has_new_entities(query, history)
    
    print(f"Query: '{query}'")
    print(f"Has new entities: {has_new_entities}")
    print(f"New entities detected: {new_entities}")
    
    # Verify OpenLab is detected
    assert has_new_entities, "Should detect new entities"
    assert "OpenLab" in new_entities, "Should detect OpenLab as new entity"
    
    # Test full classification
    result = mediator.classify(query, history, {"CONTEXTUAL_FOLLOW_UP": 0.5})
    
    print(f"Classification result: {result}")
    print(f"Needs search: {result.get('needs_search', False)}")
    print(f"Entity detection triggered: {result.get('entity_detection_triggered', False)}")
    
    # Verify search is triggered
    assert result.get('needs_search', False), "Should trigger search for new entities"
    assert result.get('entity_detection_triggered', False), "Should indicate entity detection was triggered"
    
    print("✅ OpenLab detection test PASSED!")
    return True

def test_confidence_threshold():
    """Test that the new confidence threshold works correctly."""
    print("\nTesting confidence threshold...")
    
    class MockOpenAIService:
        def get_chat_response(self, messages, max_completion_tokens=200):
            return '{"classification": "NEW_TOPIC", "needs_search": true, "confidence": 0.7, "external_entities": [], "reasoning": "Low confidence classification"}'
    
    mock_service = MockOpenAIService()
    mediator = QueryMediator(mock_service, confidence_threshold=0.6)
    
    # Test with confidence 0.5 (below threshold)
    current_classification = {"CONTEXTUAL_FOLLOW_UP": 0.5}
    should_mediate = mediator.should_mediate(current_classification)
    
    print(f"Confidence 0.5, threshold 0.6: should_mediate = {should_mediate}")
    assert should_mediate, "Should mediate when confidence (0.5) < threshold (0.6)"
    
    # Test with confidence 0.7 (above threshold)
    current_classification = {"CONTEXTUAL_FOLLOW_UP": 0.7}
    should_mediate = mediator.should_mediate(current_classification)
    
    print(f"Confidence 0.7, threshold 0.6: should_mediate = {should_mediate}")
    assert not should_mediate, "Should not mediate when confidence (0.7) >= threshold (0.6)"
    
    print("✅ Confidence threshold test PASSED!")
    return True

def test_entity_extraction():
    """Test the entity extraction functionality."""
    print("\nTesting entity extraction...")
    
    class MockOpenAIService:
        pass
    
    mock_service = MockOpenAIService()
    mediator = QueryMediator(mock_service)
    
    # Test various entity types
    test_cases = [
        ("Is it the same as OpenLab?", {"OpenLab"}),
        ("What about Docker compatibility?", {"Docker"}),
        ("How does it compare to iLab v2.1?", {"iLab"}),
        ("Can I use it with React?", {"React"}),
        ("Does it support API integration?", {"API"}),
        ("What about the SDK?", {"SDK"}),
    ]
    
    for query, expected_entities in test_cases:
        entities = mediator._extract_entities(query)
        print(f"Query: '{query}' -> Entities: {entities}")
        
        # Check if expected entities are found
        for expected in expected_entities:
            assert expected in entities, f"Should detect '{expected}' in '{query}'"
    
    print("✅ Entity extraction test PASSED!")
    return True

if __name__ == "__main__":
    print("🔧 Testing Entity Detection Fix for Memory Failure")
    print("=" * 60)
    
    try:
        # Run all tests
        test_openlab_detection()
        test_confidence_threshold()
        test_entity_extraction()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! The memory failure fix is working correctly.")
        print("\nThe system will now:")
        print("- Detect 'OpenLab' as a new entity requiring search")
        print("- Trigger search even for follow-up questions with new entities")
        print("- Use the enhanced confidence threshold (0.6) for better mediation")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
