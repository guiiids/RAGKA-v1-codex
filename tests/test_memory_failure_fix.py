#!/usr/bin/env python3
"""
Test script to validate fixes for the memory failure issue where "how do I use it?" 
was incorrectly classified as NEW_TOPIC instead of CONTEXTUAL_FOLLOW_UP.
"""

import sys
import os
import logging
from typing import List, Dict

# Add current directory to path for imports
sys.path.append('.')

# Import the fixed components
from rag_assistant_v2 import FlaskRAGAssistantV2
from enhanced_pattern_matcher import EnhancedPatternMatcher
from query_mediator import QueryMediator
from conversation_context_analyzer import ConversationContextAnalyzer
from openai_service import OpenAIService

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockOpenAIService:
    """Mock OpenAI service for testing without API calls"""
    
    def __init__(self):
        self.deployment_name = "test-deployment"
    
    def get_chat_response(self, messages, max_completion_tokens=200):
        # Mock response based on message content
        last_message = messages[-1]['content'] if messages else ""
        
        if "classification" in last_message.lower():
            # Mock mediator classification response
            return """{
                "classification": "CONTEXTUAL_FOLLOW_UP",
                "needs_search": false,
                "confidence": 0.9,
                "external_entities": [],
                "reasoning": "Query contains pronoun 'it' which refers to previously discussed topic"
            }"""
        
        # Mock regular chat response
        return "Based on the conversation context, I can help you with that."

def test_pattern_matching_fix():
    """Test that pattern matching correctly identifies contextual queries with pronouns"""
    logger.info("=== Testing Pattern Matching Fix ===")
    
    pattern_matcher = EnhancedPatternMatcher()
    
    # Test cases that should be classified as CONTEXTUAL_FOLLOW_UP
    contextual_queries = [
        "how do I use it?",
        "how can I use it?", 
        "how would I use that?",
        "how should I use this?",
        "it",
        "this",
        "that"
    ]
    
    # Test with mock conversation history
    conversation_history = [
        {"role": "user", "content": "what is ilab"},
        {"role": "assistant", "content": "iLab is a software platform..."}
    ]
    
    results = []
    for query in contextual_queries:
        query_type, confidence = pattern_matcher.classify_query(query, conversation_history)
        logger.info(f"Query: '{query}' -> Type: {query_type}, Confidence: {confidence:.2f}")
        
        # The key test: "how do I use it?" should now be CONTEXTUAL_FOLLOW_UP
        if "how do i use it" in query.lower():
            success = query_type == "CONTEXTUAL_FOLLOW_UP"
            logger.info(f"KEY TEST - 'how do I use it?' classification: {'PASS' if success else 'FAIL'}")
            results.append(success)
        else:
            # Other contextual queries should also be CONTEXTUAL_FOLLOW_UP
            results.append(query_type == "CONTEXTUAL_FOLLOW_UP")
    
    return all(results)

def test_entity_detection_fix():
    """Test that entity detection correctly identifies contextual references"""
    logger.info("=== Testing Entity Detection Fix ===")
    
    mock_openai_service = MockOpenAIService()
    query_mediator = QueryMediator(mock_openai_service, confidence_threshold=0.6)
    
    # Test contextual reference detection
    test_queries = [
        "how do I use it?",
        "what about this?",
        "tell me more about that",
        "how does it work?",
        "can I use them?"
    ]
    
    for query in test_queries:
        contextual_refs = query_mediator._detect_contextual_references(query)
        logger.info(f"Query: '{query}' -> Contextual refs: {contextual_refs}")
        
        # Should detect pronouns
        if any(pronoun in query.lower() for pronoun in ['it', 'this', 'that', 'them']):
            if not contextual_refs:
                logger.error(f"FAIL: Should have detected contextual references in '{query}'")
                return False
    
    # Test has_new_entities with contextual references
    conversation_history = [
        {"role": "user", "content": "what is openlab"},
        {"role": "assistant", "content": "OpenLab is a suite of software solutions..."}
    ]
    
    has_new, entities = query_mediator._has_new_entities("how do I use it?", conversation_history)
    logger.info(f"'how do I use it?' -> Has new entities: {has_new}, Entities: {entities}")
    
    # Should return False for new entities since "it" requires context resolution
    if has_new:
        logger.error("FAIL: Should not detect new entities for pronoun-based query")
        return False
    
    logger.info("PASS: Entity detection correctly handles contextual references")
    return True

def test_full_conversation_scenario():
    """Test the complete conversation scenario that was failing"""
    logger.info("=== Testing Full Conversation Scenario ===")
    
    # Create RAG assistant with mock OpenAI service
    rag_assistant = FlaskRAGAssistantV2()
    rag_assistant.openai_service = MockOpenAIService()
    rag_assistant.query_mediator.openai_service = MockOpenAIService()
    
    # Simulate the failing conversation scenario
    conversation_history = [
        {"role": "user", "content": "what is ilab"},
        {"role": "assistant", "content": "iLab is a software platform designed to support institutions, core facilities, and shared resources in managing their operations. It offers tools for workflows, billing, reporting, and resource management."},
        {"role": "user", "content": "What is openlab?"},
        {"role": "assistant", "content": "OpenLab is a suite of software solutions developed by Agilent Technologies, designed to support laboratory workflows and data management. It includes tools for chromatography data systems, informatics, and integration with laboratory information management systems (LIMS)."}
    ]
    
    # The problematic query
    query = "how do I use it?"
    
    # Test query type detection
    query_type = rag_assistant.detect_query_type(query, conversation_history)
    logger.info(f"Query type detected: {query_type}")
    
    # This should now be CONTEXTUAL_FOLLOW_UP, not NEW_TOPIC_*
    if query_type != "CONTEXTUAL_FOLLOW_UP":
        logger.error(f"FAIL: Expected CONTEXTUAL_FOLLOW_UP, got {query_type}")
        return False
    
    logger.info("PASS: Full conversation scenario correctly classified")
    return True

def test_edge_cases():
    """Test edge cases and boundary conditions"""
    logger.info("=== Testing Edge Cases ===")
    
    pattern_matcher = EnhancedPatternMatcher()
    
    # Test queries that should still be NEW_TOPIC_PROCEDURAL (no pronouns)
    new_topic_queries = [
        "how do I create a calendar?",
        "how can I setup the system?",
        "what are the steps to install?"
    ]
    
    for query in new_topic_queries:
        query_type, confidence = pattern_matcher.classify_query(query, [])
        logger.info(f"Query: '{query}' -> Type: {query_type}")
        
        # These should remain as NEW_TOPIC_PROCEDURAL since they don't have pronouns
        if query_type not in ["NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL"]:
            logger.error(f"FAIL: '{query}' should be NEW_TOPIC, got {query_type}")
            return False
    
    # Test mixed cases
    mixed_queries = [
        ("how do I use OpenLab?", "NEW_TOPIC_PROCEDURAL"),    # Specific product, not pronoun
        ("how do I use it with OpenLab?", "CONTEXTUAL_FOLLOW_UP"),  # Has "it" pronoun
    ]
    
    conversation_history = [
        {"role": "user", "content": "what is ilab"},
        {"role": "assistant", "content": "iLab is a platform..."}
    ]
    
    for query, expected_type in mixed_queries:
        query_type, confidence = pattern_matcher.classify_query(query, conversation_history)
        logger.info(f"Query: '{query}' -> Expected: {expected_type}, Got: {query_type}")
        
        if query_type != expected_type:
            logger.error(f"FAIL: Expected {expected_type}, got {query_type}")
            return False
    
    logger.info("PASS: Edge cases handled correctly")
    return True

def run_all_tests():
    """Run all tests and report results"""
    logger.info("========== MEMORY FAILURE FIX VALIDATION ==========")
    
    tests = [
        ("Pattern Matching Fix", test_pattern_matching_fix),
        ("Entity Detection Fix", test_entity_detection_fix),
        ("Full Conversation Scenario", test_full_conversation_scenario),
        ("Edge Cases", test_edge_cases),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
            logger.info(f"{test_name}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            logger.error(f"{test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n========== TEST RESULTS SUMMARY ==========")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED - Memory failure fix validated!")
        return True
    else:
        logger.error("❌ SOME TESTS FAILED - Review the fixes")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
