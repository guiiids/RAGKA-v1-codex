"""
Test module for Redis cache functionality in RAGKA.
"""

import unittest
import json
import time
from unittest.mock import patch, MagicMock

from services.redis_service import RedisService, redis_service
from rag_cache_wrapper import RagCacheWrapper


class TestRedisService(unittest.TestCase):
    """Test the Redis service functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock Redis client
        self.mock_redis = MagicMock()
        
        # Create a patched RedisService instance
        with patch('redis.Redis', return_value=self.mock_redis):
            self.redis_service = RedisService()
            # Force connected state
            self.redis_service._connected = True
            self.redis_service._client = self.mock_redis
    
    def test_is_connected(self):
        """Test the is_connected method."""
        # Set up the mock to return True for ping
        self.mock_redis.ping.return_value = True
        
        # Test is_connected
        self.assertTrue(self.redis_service.is_connected())
        
        # Verify ping was called
        self.mock_redis.ping.assert_called_once()
        
        # Test when ping raises an exception
        self.mock_redis.ping.side_effect = Exception("Connection error")
        self.assertFalse(self.redis_service.is_connected())
        self.assertFalse(self.redis_service._connected)
    
    def test_get(self):
        """Test the get method."""
        # Set up the mock to return a value
        self.mock_redis.get.return_value = b'{"key": "value"}'
        
        # Test get with JSON value
        result = self.redis_service.get("test_key")
        self.assertEqual(result, {"key": "value"})
        self.mock_redis.get.assert_called_with("test_key")
        
        # Test get with non-JSON value
        self.mock_redis.get.return_value = b'not json'
        result = self.redis_service.get("test_key")
        self.assertEqual(result, b'not json')
        
        # Test get with None value
        self.mock_redis.get.return_value = None
        result = self.redis_service.get("test_key")
        self.assertIsNone(result)
        
        # Test get with exception
        self.mock_redis.get.side_effect = Exception("Redis error")
        result = self.redis_service.get("test_key")
        self.assertIsNone(result)
    
    def test_set(self):
        """Test the set method."""
        # Test set with string value
        self.redis_service.set("test_key", "test_value")
        self.mock_redis.set.assert_called_with("test_key", "test_value", ex=self.redis_service.default_expiration)
        
        # Test set with JSON-serializable value
        self.redis_service.set("test_key", {"key": "value"})
        self.mock_redis.set.assert_called_with("test_key", json.dumps({"key": "value"}), ex=self.redis_service.default_expiration)
        
        # Test set with custom expiration
        self.redis_service.set("test_key", "test_value", 60)
        self.mock_redis.set.assert_called_with("test_key", "test_value", ex=60)
        
        # Test set with exception
        self.mock_redis.set.side_effect = Exception("Redis error")
        result = self.redis_service.set("test_key", "test_value")
        self.assertFalse(result)
    
    def test_delete(self):
        """Test the delete method."""
        # Set up the mock to return 1 (key deleted)
        self.mock_redis.delete.return_value = 1
        
        # Test delete
        result = self.redis_service.delete("test_key")
        self.assertTrue(result)
        self.mock_redis.delete.assert_called_with("test_key")
        
        # Test delete with no key found
        self.mock_redis.delete.return_value = 0
        result = self.redis_service.delete("test_key")
        self.assertFalse(result)
        
        # Test delete with exception
        self.mock_redis.delete.side_effect = Exception("Redis error")
        result = self.redis_service.delete("test_key")
        self.assertFalse(result)
    
    def test_health_check(self):
        """Test the health_check method."""
        # Set up the mock to return info
        self.mock_redis.info.return_value = {
            "redis_mode": "standalone",
            "redis_version": "6.2.6",
            "used_memory_human": "1.00M",
            "connected_clients": 1,
            "uptime_in_seconds": 3600
        }
        
        # Test health_check
        result = self.redis_service.health_check()
        self.assertEqual(result["connected"], True)
        self.assertEqual(result["mode"], "standalone")
        self.assertEqual(result["version"], "6.2.6")
        self.assertEqual(result["used_memory"], "1.00M")
        self.assertEqual(result["clients_connected"], 1)
        self.assertEqual(result["uptime_seconds"], 3600)
        
        # Test health_check with exception
        self.mock_redis.info.side_effect = Exception("Redis error")
        result = self.redis_service.health_check()
        self.assertEqual(result["connected"], False)
        self.assertIn("error", result)


class TestRagCacheWrapper(unittest.TestCase):
    """Test the RAG cache wrapper functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock RAG assistant
        self.mock_rag_assistant = MagicMock()
        
        # Create a mock Redis service
        self.mock_redis_service = MagicMock()
        self.mock_redis_service.is_connected.return_value = True
        self.mock_redis_service.default_expiration = 3600
        
        # Create a patched RagCacheWrapper instance
        with patch('rag_cache_wrapper.redis_service', self.mock_redis_service):
            self.cache_wrapper = RagCacheWrapper(self.mock_rag_assistant)
    
    def test_generate_embedding(self):
        """Test the generate_embedding method with caching."""
        # Set up the mock to return None for cache miss
        self.mock_redis_service.get.return_value = None
        
        # Set up the mock RAG assistant to return an embedding
        embedding = [0.1, 0.2, 0.3]
        self.mock_rag_assistant.generate_embedding.return_value = embedding
        
        # Test generate_embedding with cache miss
        result = self.cache_wrapper.generate_embedding("test_text")
        
        # Verify the cache was checked
        self.mock_redis_service.get.assert_called_once()
        
        # Verify the RAG assistant was called
        self.mock_rag_assistant.generate_embedding.assert_called_with("test_text")
        
        # Verify the result is correct
        self.assertEqual(result, embedding)
        
        # Verify the result was cached
        self.mock_redis_service.set.assert_called_once()
        
        # Reset mocks
        self.mock_redis_service.get.reset_mock()
        self.mock_redis_service.set.reset_mock()
        self.mock_rag_assistant.generate_embedding.reset_mock()
        
        # Set up the mock to return a cached embedding
        self.mock_redis_service.get.return_value = embedding
        
        # Test generate_embedding with cache hit
        result = self.cache_wrapper.generate_embedding("test_text")
        
        # Verify the cache was checked
        self.mock_redis_service.get.assert_called_once()
        
        # Verify the RAG assistant was not called
        self.mock_rag_assistant.generate_embedding.assert_not_called()
        
        # Verify the result is correct
        self.assertEqual(result, embedding)
        
        # Verify the result was not cached again
        self.mock_redis_service.set.assert_not_called()
    
    def test_search_knowledge_base(self):
        """Test the search_knowledge_base method with caching."""
        # Set up the mock to return None for cache miss
        self.mock_redis_service.get.return_value = None
        
        # Set up the mock RAG assistant to return search results
        search_results = [{"chunk": "test chunk", "title": "test title"}]
        self.mock_rag_assistant.search_knowledge_base.return_value = search_results
        
        # Test search_knowledge_base with cache miss
        result = self.cache_wrapper.search_knowledge_base("test query")
        
        # Verify the cache was checked
        self.mock_redis_service.get.assert_called_once()
        
        # Verify the RAG assistant was called
        self.mock_rag_assistant.search_knowledge_base.assert_called_with("test query")
        
        # Verify the result is correct
        self.assertEqual(result, search_results)
        
        # Verify the result was cached
        self.mock_redis_service.set.assert_called_once()
        
        # Reset mocks
        self.mock_redis_service.get.reset_mock()
        self.mock_redis_service.set.reset_mock()
        self.mock_rag_assistant.search_knowledge_base.reset_mock()
        
        # Set up the mock to return cached search results
        self.mock_redis_service.get.return_value = search_results
        
        # Test search_knowledge_base with cache hit
        result = self.cache_wrapper.search_knowledge_base("test query")
        
        # Verify the cache was checked
        self.mock_redis_service.get.assert_called_once()
        
        # Verify the RAG assistant was not called
        self.mock_rag_assistant.search_knowledge_base.assert_not_called()
        
        # Verify the result is correct
        self.assertEqual(result, search_results)
        
        # Verify the result was not cached again
        self.mock_redis_service.set.assert_not_called()
    
    def test_generate_rag_response(self):
        """Test the generate_rag_response method with caching."""
        # Set up the mock to return None for cache miss
        self.mock_redis_service.get.return_value = None
        
        # Set up the mock RAG assistant to return a response
        rag_response = ("answer", [{"id": "1", "title": "test"}], [], {}, "context")
        self.mock_rag_assistant.generate_rag_response.return_value = rag_response
        
        # Set up the mock conversation history
        self.mock_rag_assistant.conversation_manager.get_history.return_value = [{"role": "system", "content": "test"}]
        
        # Test generate_rag_response with cache miss
        result = self.cache_wrapper.generate_rag_response("test query")
        
        # Verify the conversation history was checked
        self.mock_rag_assistant.conversation_manager.get_history.assert_called_once()
        
        # Verify the cache was checked
        self.mock_redis_service.get.assert_called_once()
        
        # Verify the RAG assistant was called
        self.mock_rag_assistant.generate_rag_response.assert_called_with("test query", False)
        
        # Verify the result is correct
        self.assertEqual(result, rag_response)
        
        # Verify the result was cached
        self.mock_redis_service.set.assert_called_once()
        
        # Reset mocks
        self.mock_redis_service.get.reset_mock()
        self.mock_redis_service.set.reset_mock()
        self.mock_rag_assistant.generate_rag_response.reset_mock()
        self.mock_rag_assistant.conversation_manager.get_history.reset_mock()
        
        # Set up the mock to return cached response
        cached_response = {
            "answer": "answer",
            "cited_sources": [{"id": "1", "title": "test"}],
            "evaluation": {},
            "context": "context",
            "timestamp": time.time()
        }
        self.mock_redis_service.get.return_value = cached_response
        
        # Test generate_rag_response with cache hit
        result = self.cache_wrapper.generate_rag_response("test query")
        
        # Verify the conversation history was checked
        self.mock_rag_assistant.conversation_manager.get_history.assert_called_once()
        
        # Verify the cache was checked
        self.mock_redis_service.get.assert_called_once()
        
        # Verify the RAG assistant was not called
        self.mock_rag_assistant.generate_rag_response.assert_not_called()
        
        # Verify the result is correct
        self.assertEqual(result[0], cached_response["answer"])
        self.assertEqual(result[1], cached_response["cited_sources"])
        self.assertEqual(result[3], cached_response["evaluation"])
        self.assertEqual(result[4], cached_response["context"])
        
        # Verify the result was not cached again
        self.mock_redis_service.set.assert_not_called()
        
        # Verify the conversation history was updated
        self.mock_rag_assistant.conversation_manager.add_user_message.assert_called_with("test query")
        self.mock_rag_assistant.conversation_manager.add_assistant_message.assert_called_with(cached_response["answer"])
    
    def test_follow_up_question_not_cached(self):
        """Test that follow-up questions are not cached."""
        # Set up the mock conversation history with more than 2 messages
        self.mock_rag_assistant.conversation_manager.get_history.return_value = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"}
        ]
        
        # Set up the mock RAG assistant to return a response
        rag_response = ("answer", [{"id": "1", "title": "test"}], [], {}, "context")
        self.mock_rag_assistant.generate_rag_response.return_value = rag_response
        
        # Test generate_rag_response with follow-up question
        result = self.cache_wrapper.generate_rag_response("follow-up question")
        
        # Verify the conversation history was checked
        self.mock_rag_assistant.conversation_manager.get_history.assert_called_once()
        
        # Verify the cache was not checked
        self.mock_redis_service.get.assert_not_called()
        
        # Verify the RAG assistant was called directly
        self.mock_rag_assistant.generate_rag_response.assert_called_with("follow-up question", False)
        
        # Verify the result is correct
        self.assertEqual(result, rag_response)
        
        # Verify the result was not cached
        self.mock_redis_service.set.assert_not_called()


if __name__ == '__main__':
    unittest.main()
