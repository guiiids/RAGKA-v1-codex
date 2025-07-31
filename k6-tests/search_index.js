/**
 * k6 performance test for Azure Cognitive Search index operations.
 *
 * Usage:
 *   k6 run \
 *     --env AZURE_SEARCH_SERVICE_ENDPOINT=https://capozzol01searchservice.search.windows.net \
 *     --env AZURE_SEARCH_INDEX=vector-1751292361997-pool10 \
 *     --env AZURE_SEARCH_ADMIN_KEY=<YOUR_AZURE_SEARCH_ADMIN_KEY> \
 *     --env API_VERSION=2024-08-01-preview \
 *     k6-tests/search_index.js
 */
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 10,           // virtual users
  duration: '1m',    // total test time
};

export default function () {
  const serviceEndpoint = __ENV.AZURE_SEARCH_SERVICE_ENDPOINT;
  const indexName = __ENV.AZURE_SEARCH_INDEX;
  const apiKey = __ENV.AZURE_SEARCH_ADMIN_KEY;
  const apiVersion = __ENV.API_VERSION || '2024-08-01-preview';

  const url = `${serviceEndpoint}/indexes/${indexName}/docs/search?api-version=${apiVersion}`;
  const payload = JSON.stringify({
    search: '*',
    top: Number(__ENV.SEARCH_TOP) || 10
  });
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'api-key': apiKey,
    },
  };

  const res = http.post(url, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'search latency under 1000ms': (r) => r.timings.duration < 1000,
  });
}
