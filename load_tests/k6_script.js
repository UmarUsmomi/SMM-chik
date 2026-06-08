import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 }, // Ramp up to 20 users over 30 seconds
    { duration: '1m', target: 20 },  // Stay at 20 users for 1 minute
    { duration: '30s', target: 0 },  // Ramp down to 0 users over 30 seconds
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.01'],   // Error rate must be less than 1%
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // Test Health endpoint
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
    'health body matches': (r) => r.json().status === 'healthy',
  });

  sleep(1);

  // Test Dashboard view
  const dashboardRes = http.get(`${BASE_URL}/`);
  check(dashboardRes, {
    'dashboard status is 200': (r) => r.status === 200,
    'dashboard contains title': (r) => r.body.includes('НейроСофт Гейминг'),
  });

  sleep(2);
}
