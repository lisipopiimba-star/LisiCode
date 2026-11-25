import json
import unittest
from unittest.mock import patch
from io import BytesIO

import lisicode_integrations as api

class FakeResponse:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.body

class ElevenLabsTests(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_voice_list_uses_api_key_header(self, mocked):
        mocked.return_value = FakeResponse(json.dumps({'voices':[{'name':'Demo','voice_id':'abc','category':'premade'}]}).encode())
        result = api.elevenlabs_voices('secret-key', 5)
        self.assertEqual(result[0]['voice_id'], 'abc')
        req = mocked.call_args.args[0]
        self.assertEqual(req.get_header('Xi-api-key'), 'secret-key')

    @patch('urllib.request.urlopen')
    def test_tts_returns_mp3_bytes(self, mocked):
        mocked.return_value = FakeResponse(b'fake-mp3')
        result = api.elevenlabs_tts('secret-key', 'Hello', 'voice123')
        self.assertEqual(result, b'fake-mp3')
        req = mocked.call_args.args[0]
        self.assertIn('/text-to-speech/voice123', req.full_url)
        self.assertEqual(json.loads(req.data)['text'], 'Hello')
        self.assertEqual(req.get_header('Xi-api-key'), 'secret-key')

    def test_rejects_empty_or_oversized_text(self):
        with self.assertRaises(ValueError): api.elevenlabs_tts('key', '', 'voice')
        with self.assertRaises(ValueError): api.elevenlabs_tts('key', 'x' * 10001, 'voice')

if __name__ == '__main__': unittest.main()
