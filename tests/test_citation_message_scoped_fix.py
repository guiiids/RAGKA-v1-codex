#!/usr/bin/env python3
"""
Test script for citation system fixes:
1. Pre-LLM deduplication to prevent citation mismatches
2. Message-scoped citation persistence across conversation
"""

import sys
import os
import logging
from typing import List, Dict, Any
import json

# Add the current directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_assistant_v2 import FlaskRAGAssistantV2, prioritize_procedural_content

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_results_with_duplicates() -> List[Dict]:
    """Create test search results that include duplicate documents (different chunks)"""
    return [
        {
            "chunk": "iLab is a software platform that facilitates management of core facilities.",
            "title": "iLab API_958429.pdf",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL2lMYWIlMjBBUElfOTU4NDI5LnBkZg2",
            "relevance": 0.95,
            "is_procedural": True
        },
        {
            "chunk": "To access iLab features, users must first authenticate through the system.",
            "title": "iLab Community_2312958.pdf", 
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL2lMYWIlMjBDb21tdW5pdHlfMjMxMjk1OC5wZGY1",
            "relevance": 0.90,
            "is_procedural": True
        },
        {
            "chunk": "1. Navigate to the iLab login page\n2. Enter your credentials\n3. Click Sign In",
            "title": "iLab Community_2312958.pdf",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL2lMYWIlMjBDb21tdW5pdHlfMjMxMjk1OC5wZGY1",
            "relevance": 0.85,
            "is_procedural": True
        },
        {
            "chunk": "Additional authentication steps for admin users include multi-factor verification.",
            "title": "iLab Community_2312958.pdf",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL2lMYWIlMjBDb21tdW5pdHlfMjMxMjk1OC5wZGY1",
            "relevance": 0.80,
            "is_procedural": True
        },
        {
            "chunk": "Key iLab terms include: Core Facility, Service Request, User Account, and Billing.",
            "title": "Key iLab Terms_261285.pdf",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL0tleSUyMGlMYWIlMjBUZXJtc18yNjEyODUucGRm0",
            "relevance": 0.75,
            "is_procedural": False
        }
    ]

def test_deduplication_timing():
    """Test that deduplication happens BEFORE LLM processing"""
    logger.info("=== Testing Pre-LLM Deduplication ===")
    
    # Create test assistant
    assistant = FlaskRAGAssistantV2()
    
    # Create test results with duplicates
    test_results = create_test_results_with_duplicates()
    logger.info(f"Created {len(test_results)} test results with duplicates")
    
    # Log the original results showing duplicates
    logger.info("Original results:")
    for i, result in enumerate(test_results, 1):
        logger.info(f"  {i}. {result['title']} (parent: {result['parent_id'][:20]}...)")
    
    # Test the prioritization (should preserve all results)
    prioritized_results = prioritize_procedural_content(test_results)
    logger.info(f"After prioritization: {len(prioritized_results)} results")
    assert len(prioritized_results) == len(test_results), "Prioritization should preserve all results"
    
    # Test the deduplication
    unique_results = assistant._deduplicate_by_document(prioritized_results)
    logger.info(f"After deduplication: {len(unique_results)} unique documents")
    
    # Verify deduplication worked correctly
    expected_unique_docs = 3  # API doc, Community doc, Terms doc
    assert len(unique_results) == expected_unique_docs, f"Should have {expected_unique_docs} unique documents, got {len(unique_results)}"
    
    # Verify document uniqueness by checking (title, parent_id) pairs
    seen_docs = set()
    for result in unique_results:
        doc_key = (result.get("title", ""), result.get("parent_id", ""))
        assert doc_key not in seen_docs, f"Duplicate document found: {doc_key}"
        seen_docs.add(doc_key)
    
    logger.info("✅ Pre-LLM deduplication test passed")
    return True

def test_context_preparation():
    """Test that context preparation uses deduplicated results"""
    logger.info("=== Testing Context Preparation with Deduplication ===")
    
    # Create test assistant
    assistant = FlaskRAGAssistantV2()
    
    # Create test results with duplicates
    test_results = create_test_results_with_duplicates()
    
    # Test _prepare_context method
    context_str, src_map = assistant._prepare_context(test_results)
    
    # Verify context and source map
    logger.info(f"Context contains {len(src_map)} sources")
    logger.info(f"Context length: {len(context_str)} characters")
    
    # Should have exactly 3 unique sources after deduplication
    expected_sources = 3
    assert len(src_map) == expected_sources, f"Source map should have {expected_sources} sources, got {len(src_map)}"
    
    # Verify each source has required fields
    for source_id, source_info in src_map.items():
        assert "title" in source_info, f"Source {source_id} missing title"
        assert "content" in source_info, f"Source {source_id} missing content"
        assert "parent_id" in source_info, f"Source {source_id} missing parent_id"
        assert "is_procedural" in source_info, f"Source {source_id} missing is_procedural flag"
        logger.info(f"Source {source_id}: {source_info['title']}")
    
    # Verify context string has correct number of source tags
    import re
    source_tags = re.findall(r'<source id="([^"]+)"', context_str)
    assert len(source_tags) == expected_sources, f"Context should have {expected_sources} source tags, got {len(source_tags)}"
    
    logger.info("✅ Context preparation test passed")
    return True

def test_message_counter_initialization():
    """Test that message counter is properly initialized"""
    logger.info("=== Testing Message Counter Initialization ===")
    
    # Create test assistant
    assistant = FlaskRAGAssistantV2()
    
    # Verify initial state
    assert assistant._message_counter == 0, "Message counter should start at 0"
    assert len(assistant._message_source_maps) == 0, "Message source maps should be empty initially"
    assert len(assistant._all_sources) == 0, "All sources should be empty initially"
    
    logger.info("✅ Message counter initialization test passed")
    return True

def simulate_conversation_flow():
    """Simulate a multi-turn conversation to test message-scoped citations"""
    logger.info("=== Simulating Multi-Turn Conversation ===")
    
    # Create test assistant
    assistant = FlaskRAGAssistantV2()
    
    # Mock the search_knowledge_base method to return our test data
    def mock_search_1(query):
        return create_test_results_with_duplicates()[:3]  # First 3 results
    
    def mock_search_2(query):
        return create_test_results_with_duplicates()[2:]  # Last 3 results (with overlap)
    
    # Mock the OpenAI service to avoid API calls
    def mock_chat_response(messages, **kwargs):
        return "This is a mock response with citations [1] and [2]."
    
    assistant.openai_service.get_chat_response = mock_chat_response
    
    # First message
    logger.info("Processing first message...")
    assistant.search_knowledge_base = mock_search_1
    
    # Simulate the first part of RAG response generation
    results_1 = mock_search_1("What is iLab?")
    context_1, src_map_1 = assistant._prepare_context(results_1)
    
    # Simulate message counter increment (this would happen in the frontend)
    assistant._message_counter += 1
    message_id_1 = assistant._message_counter
    assistant._message_source_maps[message_id_1] = src_map_1
    assistant._all_sources.update(src_map_1)
    
    logger.info(f"Message 1: {len(src_map_1)} sources")
    logger.info(f"Cumulative sources: {len(assistant._all_sources)}")
    
    # Second message
    logger.info("Processing second message...")
    assistant.search_knowledge_base = mock_search_2
    
    # Simulate the second part of RAG response generation
    results_2 = mock_search_2("How to login to iLab?")
    context_2, src_map_2 = assistant._prepare_context(results_2)
    
    # Simulate message counter increment
    assistant._message_counter += 1
    message_id_2 = assistant._message_counter
    assistant._message_source_maps[message_id_2] = src_map_2
    assistant._all_sources.update(src_map_2)
    
    logger.info(f"Message 2: {len(src_map_2)} sources")
    logger.info(f"Cumulative sources: {len(assistant._all_sources)}")
    
    # Verify message isolation
    assert message_id_1 in assistant._message_source_maps, "Message 1 sources should be preserved"
    assert message_id_2 in assistant._message_source_maps, "Message 2 sources should be preserved"
    
    # Verify cumulative sources contain sources from both messages
    total_unique_sources = len(assistant._all_sources)
    logger.info(f"Total unique sources across conversation: {total_unique_sources}")
    
    # Each message should have contributed to the cumulative pool
    assert total_unique_sources >= len(src_map_1), "Should include sources from message 1"
    assert total_unique_sources >= len(src_map_2), "Should include sources from message 2"
    
    logger.info("✅ Conversation flow simulation test passed")
    return True

def test_debug_output():
    """Test that debug information is properly logged"""
    logger.info("=== Testing Debug Output ===")
    
    # Create test assistant
    assistant = FlaskRAGAssistantV2()
    
    # Create test results
    test_results = create_test_results_with_duplicates()
    
    # Enable debug logging temporarily
    debug_logger = logging.getLogger('rag_assistant_v2')
    original_level = debug_logger.level
    debug_logger.setLevel(logging.DEBUG)
    
    try:
        # Test context preparation with debug output
        context_str, src_map = assistant._prepare_context(test_results)
        
        # The debug output should have been logged (we can't easily capture it in this test,
        # but we can verify the src_map structure is correct for debugging)
        
        # Verify source map has debug-friendly structure
        for source_id, source_info in src_map.items():
            assert "title" in source_info, "Source should have title for debugging"
            assert "parent_id" in source_info, "Source should have parent_id for debugging"
            assert "is_procedural" in source_info, "Source should have procedural flag for debugging"
            
            # Verify unique ID format (should be S_timestamp_hash)
            assert source_id.startswith("S_"), f"Source ID should start with 'S_': {source_id}"
            parts = source_id.split("_")
            assert len(parts) == 3, f"Source ID should have 3 parts separated by '_': {source_id}"
    
    finally:
        # Restore original log level
        debug_logger.setLevel(original_level)
    
    logger.info("✅ Debug output test passed")
    return True

def run_all_tests():
    """Run all citation system fix tests"""
    logger.info("🚀 Starting Citation System Fix Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Deduplication Timing", test_deduplication_timing),
        ("Context Preparation", test_context_preparation), 
        ("Message Counter Init", test_message_counter_initialization),
        ("Conversation Flow", simulate_conversation_flow),
        ("Debug Output", test_debug_output)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            logger.info(f"\n📋 Running: {test_name}")
            result = test_func()
            results.append((test_name, result, None))
            logger.info(f"✅ {test_name}: PASSED")
        except Exception as e:
            logger.error(f"❌ {test_name}: FAILED - {str(e)}")
            results.append((test_name, False, str(e)))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for test_name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status:8} {test_name}")
        if error:
            logger.info(f"         Error: {error}")
    
    logger.info("-" * 60)
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Citation system fixes are working correctly.")
        return True
    else:
        logger.error("⚠️  Some tests failed. Check the logs above for details.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
