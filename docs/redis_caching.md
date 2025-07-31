# Redis Caching for RAGKA

This document describes the Redis caching implementation for the RAGKA system. Redis is used to cache search results, embeddings, and RAG responses to improve performance and reduce latency.

## Overview

The Redis caching implementation consists of the following components:

1. **Redis Service**: A service that provides a simple interface to Redis operations.
2. **RAG Cache Wrapper**: A wrapper around the RAG assistant that adds caching functionality.
3. **Docker Configuration**: Redis is included in the Docker container for easy deployment.

## Redis Service

The Redis service (`services/redis_service.py`) provides a simple interface to Redis operations. It handles connection management, serialization/deserialization of values, and error handling. The service is implemented as a singleton instance that can be imported and used throughout the application.

### Configuration

The Redis service is configured using environment variables:

- `REDIS_HOST`: The hostname of the Redis server (default: `localhost`)
- `REDIS_PORT`: The port of the Redis server (default: `6379`)
- `REDIS_DB`: The Redis database number (default: `0`)
- `REDIS_PASSWORD`: The password for the Redis server (default: `None`)
- `REDIS_DEFAULT_EXPIRATION`: The default expiration time in seconds for cached values (default: `3600`)

These variables can be set in the `.env` file or as environment variables in the deployment environment.

### Usage

The Redis service provides the following methods:

- `is_connected()`: Check if connected to Redis
- `reconnect()`: Attempt to reconnect to Redis if not connected
- `get(key)`: Get a value from Redis
- `set(key, value, expiration)`: Set a value in Redis
- `delete(key)`: Delete a value from Redis
- `flush_all()`: Flush all keys from the current database
- `health_check()`: Get Redis health information
- `keys(pattern)`: Get keys matching a pattern
- `delete_pattern(pattern)`: Delete all keys matching a pattern
- `get_stats()`: Get Redis statistics

## RAG Cache Wrapper

The RAG cache wrapper (`rag_cache_wrapper.py`) wraps the RAG assistant to add caching functionality. It intercepts calls to the RAG assistant and checks the cache before delegating to the wrapped instance. The wrapper caches:

1. **Embeddings**: Generated embeddings for queries and documents
2. **Search Results**: Results from the knowledge base search
3. **RAG Responses**: Generated responses for user queries

### Cache Keys

Cache keys are generated based on the input data:

- Embedding cache keys: `ragka:embedding:<md5(text)>`
- Search cache keys: `ragka:search:<md5(query)>`
- Response cache keys: `ragka:response:<md5(query+is_enhanced)>`

### Expiration Times

Different types of cached data have different expiration times:

- Embeddings: 7 days (604800 seconds)
- Search results: 24 hours (86400 seconds)
- RAG responses: 12 hours (43200 seconds)

These values can be customized by modifying the `rag_cache_wrapper.py` file.

### Follow-up Questions

Follow-up questions are not cached because they depend on the conversation history. The wrapper detects follow-up questions by checking if there are more than 2 messages in the conversation history (system message + 1 turn).

## Docker Configuration

Redis is included in the Docker container for easy deployment. The Dockerfile installs Redis and configures it to start when the container starts. The Redis server is configured to:

- Listen on localhost (127.0.0.1)
- Use the default port (6379)
- Run in daemonized mode
- Store data in `/var/lib/redis`
- Log to `/var/log/redis/redis-server.log`

The startup script (`startup.sh`) starts Redis before starting the application and checks that Redis is running properly.

## API Endpoints

The following API endpoints are available for interacting with the cache:

- `GET /api/cache/stats`: Get cache statistics
- `POST /api/cache/clear`: Clear the cache (optionally by type)

### Cache Statistics

The `/api/cache/stats` endpoint returns information about the Redis cache, including:

- `enabled`: Whether caching is enabled
- `connected`: Whether connected to Redis
- `mode`: Redis mode (standalone, cluster, etc.)
- `version`: Redis version
- `used_memory`: Memory used by Redis
- `clients_connected`: Number of connected clients
- `uptime_seconds`: Redis uptime in seconds

Example response:

```json
{
  "success": true,
  "stats": {
    "enabled": true,
    "connected": true,
    "mode": "standalone",
    "version": "6.2.6",
    "used_memory": "1.00M",
    "clients_connected": 1,
    "uptime_seconds": 3600
  }
}
```

### Clearing the Cache

The `/api/cache/clear` endpoint clears the cache. You can optionally specify a cache type to clear only specific types of cached data:

- `search`: Clear only search results
- `embedding`: Clear only embeddings
- `response`: Clear only RAG responses

Example request:

```json
{
  "type": "search"
}
```

Example response:

```json
{
  "success": true
}
```

## Testing

The Redis caching implementation includes unit tests in `tests/test_redis_cache.py`. These tests verify that:

1. The Redis service works correctly
2. The RAG cache wrapper correctly caches and retrieves data
3. Follow-up questions are not cached

To run the tests:

```bash
python -m unittest tests/test_redis_cache.py
```

## Performance Considerations

Redis caching can significantly improve performance, especially for frequently accessed data. However, there are some considerations:

1. **Memory Usage**: Redis stores all data in memory, so monitor memory usage to ensure it doesn't exceed available resources.
2. **Cache Invalidation**: The cache is invalidated based on expiration times. If the underlying data changes frequently, you may need to adjust expiration times or implement more sophisticated invalidation strategies.
3. **Cold Start**: When the cache is empty (e.g., after a restart), performance will be slower until the cache is populated.

## Troubleshooting

If you encounter issues with Redis caching, check the following:

1. **Redis Connection**: Verify that Redis is running and accessible. Use the `/api/cache/stats` endpoint to check the connection status.
2. **Cache Keys**: If data is not being cached or retrieved correctly, check the cache keys being generated.
3. **Memory Usage**: If Redis is running out of memory, increase the available memory or reduce the amount of data being cached.
4. **Logs**: Check the application logs for Redis-related errors or warnings.

## Future Improvements

Potential future improvements to the Redis caching implementation:

1. **Distributed Caching**: Support for Redis Cluster for distributed caching across multiple nodes.
2. **Cache Warming**: Proactively populate the cache with frequently accessed data.
3. **Cache Analytics**: More detailed analytics on cache hit/miss rates and performance improvements.
4. **Selective Caching**: More sophisticated rules for what to cache based on query characteristics.
5. **Cache Compression**: Compress cached data to reduce memory usage.
