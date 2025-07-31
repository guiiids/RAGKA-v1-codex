"""
Test script to demonstrate Redis caching functionality in RAGKA.

This script creates a RAG assistant, wraps it with the Redis cache wrapper,
and performs some operations to demonstrate caching.

Usage:
    python test_redis_caching.py
"""

import time
import logging
from rag_assistant_v2 import FlaskRAGAssistantV2
from rag_cache_wrapper import RagCacheWrapper
from services.redis_service import redis_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test the Redis connection."""
    logger.info("Testing Redis connection...")
    
    if redis_service.is_connected():
        logger.info("Redis is connected!")
        
        # Get Redis info
        info = redis_service.health_check()
        logger.info(f"Redis version: {info.get('version', 'unknown')}")
        logger.info(f"Redis mode: {info.get('mode', 'unknown')}")
        logger.info(f"Redis memory used: {info.get('used_memory', 'unknown')}")
        logger.info(f"Redis clients connected: {info.get('clients_connected', 0)}")
        logger.info(f"Redis uptime: {info.get('uptime_seconds', 0)} seconds")
        
        return True
    else:
        logger.error("Redis is not connected!")
        return False

def test_embedding_caching(rag_cache):
    """Test embedding caching."""
    logger.info("\nTesting embedding caching...")
    
    # Generate an embedding
    text = "This is a test text for embedding caching"
    
    logger.info(f"Generating embedding for: '{text}'")
    start_time = time.time()
    embedding = rag_cache.generate_embedding(text)
    first_time = time.time() - start_time
    logger.info(f"First embedding generation took {first_time:.4f} seconds")
    
    # Generate the same embedding again (should be cached)
    logger.info(f"Generating embedding again for: '{text}'")
    start_time = time.time()
    embedding_cached = rag_cache.generate_embedding(text)
    second_time = time.time() - start_time
    logger.info(f"Second embedding generation took {second_time:.4f} seconds")
    
    # Check if the second call was faster (indicating it was cached)
    if second_time < first_time:
        logger.info("Embedding caching is working! Second call was faster.")
        return True
    else:
        logger.warning("Embedding caching may not be working. Second call was not faster.")
        return False

def test_search_caching(rag_cache):
    """Test search caching."""
    logger.info("\nTesting search caching...")
    
    # Perform a search
    query = "What is RAGKA?"
    
    logger.info(f"Searching for: '{query}'")
    start_time = time.time()
    results = rag_cache.search_knowledge_base(query)
    first_time = time.time() - start_time
    logger.info(f"First search took {first_time:.4f} seconds")
    logger.info(f"Found {len(results)} results")
    
    # Perform the same search again (should be cached)
    logger.info(f"Searching again for: '{query}'")
    start_time = time.time()
    results_cached = rag_cache.search_knowledge_base(query)
    second_time = time.time() - start_time
    logger.info(f"Second search took {second_time:.4f} seconds")
    
    # Check if the second call was faster (indicating it was cached)
    if second_time < first_time:
        logger.info("Search caching is working! Second call was faster.")
        return True
    else:
        logger.warning("Search caching may not be working. Second call was not faster.")
        return False

def test_response_caching(rag_cache):
    """Test response caching."""
    logger.info("\nTesting response caching...")
    
    # Clear conversation history to ensure we're not dealing with follow-up questions
    rag_cache.clear_conversation_history()
    
    # Generate a response
    query = "What is a retrieval-augmented generation system?"
    
    logger.info(f"Generating response for: '{query}'")
    start_time = time.time()
    answer, cited_sources, _, evaluation, context = rag_cache.generate_rag_response(query)
    first_time = time.time() - start_time
    logger.info(f"First response generation took {first_time:.4f} seconds")
    logger.info(f"Answer length: {len(answer)} characters")
    logger.info(f"Number of cited sources: {len(cited_sources)}")
    
    # Clear conversation history again to ensure we're not dealing with follow-up questions
    rag_cache.clear_conversation_history()
    
    # Generate the same response again (should be cached)
    logger.info(f"Generating response again for: '{query}'")
    start_time = time.time()
    answer_cached, cited_sources_cached, _, evaluation_cached, context_cached = rag_cache.generate_rag_response(query)
    second_time = time.time() - start_time
    logger.info(f"Second response generation took {second_time:.4f} seconds")
    
    # Check if the second call was faster (indicating it was cached)
    if second_time < first_time:
        logger.info("Response caching is working! Second call was faster.")
        return True
    else:
        logger.warning("Response caching may not be working. Second call was not faster.")
        return False

def test_follow_up_not_cached(rag_cache):
    """Test that follow-up questions are not cached."""
    logger.info("\nTesting that follow-up questions are not cached...")
    
    # Clear conversation history
    rag_cache.clear_conversation_history()
    
    # Generate a response for the first question
    first_query = "What is RAGKA?"
    
    logger.info(f"Generating response for first question: '{first_query}'")
    start_time = time.time()
    answer, cited_sources, _, evaluation, context = rag_cache.generate_rag_response(first_query)
    first_time = time.time() - start_time
    logger.info(f"First response generation took {first_time:.4f} seconds")
    
    # Generate a response for a follow-up question
    follow_up_query = "How does it work?"
    
    logger.info(f"Generating response for follow-up question: '{follow_up_query}'")
    start_time = time.time()
    answer_follow_up, cited_sources_follow_up, _, evaluation_follow_up, context_follow_up = rag_cache.generate_rag_response(follow_up_query)
    follow_up_time = time.time() - start_time
    logger.info(f"Follow-up response generation took {follow_up_time:.4f} seconds")
    
    # Generate the same follow-up question again (should NOT be cached)
    logger.info(f"Generating response again for follow-up question: '{follow_up_query}'")
    start_time = time.time()
    answer_follow_up_again, cited_sources_follow_up_again, _, evaluation_follow_up_again, context_follow_up_again = rag_cache.generate_rag_response(follow_up_query)
    follow_up_again_time = time.time() - start_time
    logger.info(f"Second follow-up response generation took {follow_up_again_time:.4f} seconds")
    
    # Check if the second follow-up call took about the same time as the first
    # (indicating it was not cached)
    if abs(follow_up_again_time - follow_up_time) < follow_up_time * 0.5:
        logger.info("Follow-up question caching behavior is correct! Follow-up questions are not cached.")
        return True
    else:
        logger.warning("Follow-up question caching behavior may not be correct.")
        return False

def test_cache_stats(rag_cache):
    """Test cache statistics."""
    logger.info("\nTesting cache statistics...")
    
    # Get cache stats
    stats = rag_cache.get_cache_stats()
    
    logger.info(f"Cache enabled: {stats.get('enabled', False)}")
    logger.info(f"Cache connected: {stats.get('connected', False)}")
    logger.info(f"Cache mode: {stats.get('mode', 'unknown')}")
    logger.info(f"Cache version: {stats.get('version', 'unknown')}")
    logger.info(f"Cache memory used: {stats.get('used_memory', 'unknown')}")
    logger.info(f"Cache clients connected: {stats.get('clients_connected', 0)}")
    logger.info(f"Cache uptime: {stats.get('uptime_seconds', 0)} seconds")
    
    return stats.get('connected', False)

def main():
    """Main function to run the tests."""
    logger.info("Starting Redis caching tests...")
    
    # Test Redis connection
    if not test_redis_connection():
        logger.error("Redis connection test failed. Exiting.")
        return
    
    # Create a RAG assistant
    logger.info("Creating RAG assistant...")
    rag_assistant = FlaskRAGAssistantV2()
    
    # Wrap it with the Redis cache wrapper
    logger.info("Wrapping RAG assistant with Redis cache wrapper...")
    rag_cache = RagCacheWrapper(rag_assistant)
    
    # Run the tests
    embedding_test = test_embedding_caching(rag_cache)
    search_test = test_search_caching(rag_cache)
    response_test = test_response_caching(rag_cache)
    follow_up_test = test_follow_up_not_cached(rag_cache)
    stats_test = test_cache_stats(rag_cache)

    # BEGIN: Conversation intelligence debug test
    try:
        logger.info("\nTesting ConversationIntelligenceManager Redis debug info...")
        from services.conversation_intelligence import conversation_intelligence

        session_id = "testdebug"
        test_query = "Compare iLab and OpenLab"
        test_response = "iLab provides basic knowledge bases; OpenLab provides manuals and troubleshooting."
        test_classification = "CONTEXTUAL_WITH_SEARCH"

        # Write context and entities and verify via debug
        conversation_intelligence.update_conversation_context(
            session_id, test_query, test_response, test_classification
        )
        debug_info = conversation_intelligence.get_session_debug_info(session_id)
        logger.info(f"Conversation Intelligence Redis Debug Output: {debug_info}")
    except Exception as ci_debug_err:
        logger.error(f"Error during Conversation Intelligence debug test: {ci_debug_err}")
    # END: Conversation intelligence debug test

    # Print summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Redis Connection: {'PASS' if redis_service.is_connected() else 'FAIL'}")
    logger.info(f"Embedding Caching: {'PASS' if embedding_test else 'FAIL'}")
    logger.info(f"Search Caching: {'PASS' if search_test else 'FAIL'}")
    logger.info(f"Response Caching: {'PASS' if response_test else 'FAIL'}")
    logger.info(f"Follow-up Not Cached: {'PASS' if follow_up_test else 'FAIL'}")
    logger.info(f"Cache Stats: {'PASS' if stats_test else 'FAIL'}")
    
    # Overall result
    all_tests = [
        redis_service.is_connected(),
        embedding_test,
        search_test,
        response_test,
        follow_up_test,
        stats_test
    ]
    
    if all(all_tests):
        logger.info("\nAll tests PASSED! Redis caching is working correctly.")
    else:
        logger.warning("\nSome tests FAILED. Redis caching may not be working correctly.")

if __name__ == "__main__":
    main()
