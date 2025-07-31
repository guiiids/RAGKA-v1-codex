/**
 * k6 performance test for /api/query endpoint.
 *
 * Usage:
 *   k6 run --env TARGET_HOST=localhost --env TARGET_PORT=5001 k6-tests/query_flow.js
 */
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 30,           // virtual users (concurrent requests)
  duration: '1m',    // total test time
};

export default function () {
  const host = __ENV.TARGET_HOST || 'localhost';
  const port = __ENV.TARGET_PORT || '5001';
  const url = `http://${host}:${port}/api/query`;
  const payload = JSON.stringify({
    query: 'Troubleshoot Agilent GC.'
  });
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post(url, payload, params);

    check(res, {
    'status is 200':      (r) => r.status === 200,
    'latency under 2s':   (r) => r.timings.duration < 2000,
    'latency under 5s':   (r) => r.timings.duration < 5000,
    'latency under 10s':  (r) => r.timings.duration < 10000,
  });
}
