"""Executable tests against the actual Flask routes (run after pip install -r requirements.txt)."""
import unittest
import uuid
from app import app, SCENARIOS

class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.header = {'X-Lab-Session': str(uuid.uuid4())}

    def test_home_and_health(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        r = self.client.get('/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['status'], 'UP')

    def test_all_50_http_status_and_log_correlation(self):
        self.assertEqual(sum(map(len, SCENARIOS.values())), 50)
        for project, rows in SCENARIOS.items():
            for sid, name, expected_status, *_ in rows:
                with self.subTest(project=project, scenario=sid):
                    resp = self.client.post('/api/http-test', json={'project':project,'scenario':sid}, headers=self.header)
                    self.assertEqual(resp.status_code, expected_status)
                    data = resp.get_json()
                    rid = data['requestId']
                    self.assertEqual(resp.headers.get('X-Request-ID'), rid)
                    access = self.client.get('/api/logs/access.log', headers=self.header, query_string={'q':rid}).get_json()
                    application = self.client.get('/api/logs/application.log', headers=self.header, query_string={'q':rid}).get_json()
                    self.assertTrue(access['lines'])
                    self.assertTrue(application['lines'])

    def test_reset_and_download(self):
        self.client.post('/api/simulate', json={'project':'IBS','scenario':'transfer_500'}, headers=self.header)
        dl = self.client.get('/api/download/application.log', headers=self.header)
        self.assertEqual(dl.status_code,200)
        self.assertIn(b'SQLRecoverableException',dl.data)
        self.client.post('/api/reset', headers=self.header)
        self.assertEqual(self.client.get('/api/history', headers=self.header).get_json(), [])

    def test_invalid_and_missing_session(self):
        self.assertEqual(self.client.post('/api/http-test',json={'project':'IBS','scenario':'balance_ok'}).status_code,400)
        self.assertEqual(self.client.post('/api/http-test',json={'project':'IBS','scenario':'not-a-scenario'}, headers=self.header).status_code,400)

if __name__ == '__main__':
    unittest.main()
