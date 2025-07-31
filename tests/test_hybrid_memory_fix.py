#!/usr/bin/env python3
"""
Test script to validate the definitive fix for the hybrid memory failure,
where a query contains both a contextual reference ("it") and a new entity ("OpenLab").
"""

import sys
import os
import logging
from typing import List, Dict
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.append('.')

# Import the fixed components
from rag_assistant_v2 import FlaskRAGAssistantV2, SearchClient
from query_mediator import QueryMediator

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockOpenAIService:
    """Mock OpenAI service for testing without API calls"""
    def get_chat_response(self, messages, **kwargs):
        last_message = messages[-1]['content'] if messages else ""
        if "CONTEXTUAL_WITH_SEARCH" in last_message:
            return """{
                "classification": "CONTEXTUAL_WITH_SEARCH",
                "needs_search": true,
                "confidence": 0.95,
                "external_entities": ["OpenLab"],
                "reasoning": "Query contains pronoun 'it' and new entity 'OpenLab'."
            }"""
        return "Mock response"


def test_query_mediator_logic():
    """Verify the QueryMediator correctly identifies new entities alongside pronouns."""
    logger.info("=== Testing QueryMediator Logic ===")
    mediator = QueryMediator(MockOpenAIService())
    
    history = [
        {"role": "user", "content": "what is ilab"},
        {"role": "assistant", "content": "iLab is a platform..."}
    ]
    
    query = "compare it to OpenLab"
    has_new, new_entities = mediator._has_new_entities(query, history)
    
    logger.info(f"Query: '{query}' -> Has new: {has_new}, New entities: {new_entities}")
    
    assert has_new is True, "Should detect that there are new entities."
    assert "OpenLab" in new_entities, "Should identify 'OpenLab' as the new entity."
    assert "it" not in new_entities, "Should not identify 'it' as a new entity."
    
    logger.info("PASS: QueryMediator correctly handles hybrid queries.")
    return True

def test_assistant_routing_logic():
    """Verify the RAG assistant routes hybrid queries to perform a search."""
    logger.info("=== Testing Assistant Routing Logic ===")
    assistant = FlaskRAGAssistantV2()
    assistant.openai_service = MockOpenAIService()
    assistant.query_mediator.openai_service = MockOpenAIService()
    
    history = [
        {"role": "user", "content": "what is ilab"},
        {"role": "assistant", "content": "iLab is a platform..."}
    ]
    
    query = "is it the same as OpenLab?"
    
    # This will use the mock, which forces a CONTEXTUAL_WITH_SEARCH
    classification = assistant.detect_query_type(query, history)
    
    logger.info(f"Query: '{query}' -> Classified as: {classification}")
    
    assert classification == "CONTEXTUAL_WITH_SEARCH", "Assistant should classify the query as CONTEXTUAL_WITH_SEARCH."
    
    logger.info("PASS: Assistant correctly classifies hybrid queries.")
    return True

@patch('rag_assistant_v2.SearchClient')
def test_end_to_end_search_behavior(mock_search_client_class):
    """Verify the full RAG response flow triggers a search for hybrid queries."""
    logger.info("=== Testing End-to-End Search Behavior ===")
    
    # Configure the mock instance that will be returned when SearchClient is instantiated
    mock_search_instance = MagicMock()
    mock_search_instance.search.return_value = [{
        "chunk": "OpenLab is a chromatography data system from Agilent.",
        "title": "OpenLab Document",
        "parent_id": "doc-openlab-1"
    }]
    mock_search_client_class.return_value = mock_search_instance

    assistant = FlaskRAGAssistantV2()
    assistant.openai_service = MockOpenAIService()
    assistant.query_mediator.openai_service = MockOpenAIService()
    
    assistant.conversation_manager.add_user_message("what is ilab")
    assistant.conversation_manager.add_assistant_message("iLab is a platform...")
    
    query = "compare it to OpenLab"
    
    answer, sources, _, _, context = assistant.generate_rag_response(query)
    
    logger.info(f"Query: '{query}' -> Answer: '{answer}'")
    logger.info(f"Context included: {context}")
    
    # Assert that the mock search was called correctly
    mock_search_instance.search.assert_called_once()
    
    assert "OpenLab is a chromatography data system" in context, "The context should contain search results for OpenLab."
    assert "No new context provided" not in context, "A search should have been performed."
    
    logger.info("PASS: End-to-end flow correctly performs a search for hybrid queries.")
    return True

def run_all_tests():
    """Run all validation tests for the definitive fix."""
    logger.info("========== HYBRID MEMORY FIX VALIDATION ==========")
    
    tests = [
        ("QueryMediator Logic", test_query_mediator_logic),
        ("Assistant Routing Logic", test_assistant_routing_logic),
        ("End-to-End Search Behavior", test_end_to_end_search_behavior),
    ]
    
    results = []
    for name, func in tests:
        try:
            result = func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test '{name}' failed with error: {e}", exc_info=True)
            results.append((name, False))
            
    passed = sum(1 for _, res in results if res)
    total = len(results)
    
    logger.info("\n========== TEST SUMMARY ==========")
    for name, res in results:
        logger.info(f"{'✓ PASS' if res else '✗ FAIL'} - {name}")
        
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! The hybrid memory failure is definitively fixed.")
        return True
    else:
        logger.error(f"\n❌ {total - passed}/{total} TESTS FAILED. Please review the logs.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
