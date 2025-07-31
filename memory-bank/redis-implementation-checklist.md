# Redis Implementation Checklist

This checklist helps verify that the Redis caching implementation is working correctly. Follow these steps to ensure that Redis is properly configured and functioning.

## Prerequisites

- [ ] Docker is installed and running
- [ ] Redis client tools are installed (optional, for direct Redis inspection)

## Configuration Verification

- [ ] `.env` file contains Redis configuration variables:
  - [ ] `REDIS_HOST` (default: `localhost`)
  - [ ] `REDIS_PORT` (default: `6379`)
  - [ ] `REDIS_PASSWORD` (if required)
  - [ ] `REDIS_SSL` (default: `False`)
  - [ ] `REDIS_CACHE_EXPIRATION` (default: `3600`)

- [ ] Dockerfile includes Redis installation and configuration:
  - [ ] Redis server package is installed
  - [ ] Redis configuration file is created
  - [ ] Redis data and log directories are created

- [ ] `startup.sh` script starts Redis before the application:
  - [ ] Redis server is started with the configuration file
  - [ ] Redis connection is verified with a ping

## Implementation Verification

- [ ] Redis service is implemented:
  - [ ] `services/redis_service.py` file exists
  - [ ] `RedisService` class provides Redis operations
  - [ ] Singleton instance is created for application-wide use

- [ ] RAG cache wrapper is implemented:
  - [ ] `rag_cache_wrapper.py` file exists
  - [ ] `RagCacheWrapper` class wraps the RAG assistant
  - [ ] Caching is implemented for embeddings, search results, and responses

- [ ] Main application integrates the cache wrapper:
  - [ ] `main.py` imports the cache wrapper
  - [ ] RAG assistant is wrapped with the cache wrapper
  - [ ] API endpoints for cache statistics and management are implemented

## Functional Testing

- [ ] Run the test script to verify caching functionality:
  ```bash
  python test_redis_caching.py
  ```
  - [ ] Redis connection test passes
  - [ ] Embedding caching test passes
  - [ ] Search caching test passes
  - [ ] Response caching test passes
  - [ ] Follow-up question test passes
  - [ ] Cache statistics test passes

- [ ] Run the unit tests to verify the implementation:
  ```bash
  python -m unittest tests/test_redis_cache.py
  ```
  - [ ] All tests pass

## Manual Verification

- [ ] Start the application:
  ```bash
  python main.py
  ```

- [ ] Access the application in a browser:
  - [ ] Application loads correctly
  - [ ] Submit a query and verify it works
  - [ ] Submit the same query again and verify it's faster (cached)

- [ ] Check cache statistics:
  - [ ] Access `/api/cache/stats` endpoint
  - [ ] Verify Redis is connected
  - [ ] Check cache statistics

- [ ] Clear the cache:
  - [ ] Access `/api/cache/clear` endpoint
  - [ ] Verify cache is cleared
  - [ ] Submit a query again and verify it's slower (not cached)

## Docker Deployment Verification

- [ ] Build the Docker image:
  ```bash
  docker build -t ragka-redis .
  ```

- [ ] Run the Docker container:
  ```bash
  docker run -p 5001:5001 ragka-redis
  ```

- [ ] Verify Redis is running in the container:
  ```bash
  docker exec -it <container_id> redis-cli ping
  ```
  - [ ] Response should be `PONG`

- [ ] Access the application in a browser:
  - [ ] Application loads correctly
  - [ ] Submit a query and verify it works
  - [ ] Submit the same query again and verify it's faster (cached)

## Troubleshooting

If any of the above checks fail, try the following:

- [ ] Check Redis logs:
  ```bash
  docker exec -it <container_id> cat /var/log/redis/redis-server.log
  ```

- [ ] Check application logs:
  ```bash
  docker exec -it <container_id> cat logs/main_alternate.log
  ```

- [ ] Verify Redis is running:
  ```bash
  docker exec -it <container_id> ps aux | grep redis
  ```

- [ ] Check Redis configuration:
  ```bash
  docker exec -it <container_id> cat /etc/redis/redis.conf
  ```

- [ ] Verify Redis connection from the application:
  ```bash
  curl http://localhost:5001/api/cache/stats
  ```

## Rollback Procedure

If you need to disable Redis caching:

1. Set `REDIS_HOST` to an invalid value in `.env`:
   ```
   REDIS_HOST=disabled
   ```

2. Restart the application:
   ```bash
   docker restart <container_id>
   ```

3. Verify Redis is disabled:
   ```bash
   curl http://localhost:5001/api/cache/stats
   ```
   - Response should show `"connected": false`
