import json
import os
import tempfile
import time
import unittest
import urllib.error
import urllib.request

import lisicode

class DummyAgent:
    chat_id = 'web-smoke-chat'
    model = 'mock-model'

class WebUITests(unittest.TestCase):
    def setUp(self):
        self.browser_patcher = unittest.mock.patch('lisicode.webbrowser.open', return_value=False)
        self.browser_patcher.start()
        self.addCleanup(self.browser_patcher.stop)
        self.queue = lisicode.queue.Queue()
        self.agent = DummyAgent()
        self.ui = lisicode.WebUI(self.agent, self.queue)
        self.ui.start()
        self.base = 'http://127.0.0.1:' + str(self.ui.web_server.server_address[1])
        self.headers = {'X-Lisi-Token': self.ui.token, 'Content-Type': 'application/json'}

    def tearDown(self):
        self.ui.stop()

    def get(self, path):
        req = urllib.request.Request(self.base + path, headers=self.headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers=self.headers, method='POST')
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())

    def test_local_page_and_auth(self):
        with urllib.request.urlopen(self.base + '/') as response:
            self.assertIn('LisiCode', response.read().decode())
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base + '/api/chats')
        self.assertIn('chats', self.get('/api/chats'))

    def test_task_and_new_chat_queue(self):
        self.post('/api/task', {'task': 'hello'})
        self.assertEqual(self.queue.get(timeout=1), {'type': 'task', 'text': 'hello'})
        result = self.post('/api/new', {})
        self.assertEqual(self.queue.get(timeout=1), {'type': 'new', 'id': result['chat']})

    def test_approval_can_be_confirmed_from_web(self):
        approval = self.ui.create_approval('approve this')
        self.assertEqual(self.get('/api/pending')['approvals'][0]['id'], approval['id'])
        self.post('/api/approve', {'id': approval['id'], 'approved': True})
        self.assertTrue(approval['event'].wait(0.5))
        self.assertTrue(approval['approved'])

if __name__ == '__main__':
    unittest.main()
