import io, json, os, sys, tempfile, unittest, urllib.error
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lisicode


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def sse(*chunks):
    out = b''
    for c in chunks:
        out += b'data: ' + (c if isinstance(c, bytes) else json.dumps(c).encode()) + b'\n\n'
    return FakeResp(out + b'data: [DONE]\n\n')


class StreamTests(unittest.TestCase):
    def test_text_stream(self):
        resp = sse({'choices': [{'delta': {'content': 'При'}}]}, {'choices': [{'delta': {'content': 'вет'}}]},
                   {'choices': [], 'usage': {'total_tokens': 7}})
        with mock.patch('urllib.request.urlopen', return_value=resp):
            r = lisicode.api_stream('k', {'model': 'm', 'messages': []})
        self.assertEqual(r['choices'][0]['message']['content'], 'Привет')
        self.assertEqual(r['usage']['total_tokens'], 7)
        self.assertTrue(r['_streamed'])

    def test_tool_call_assembled_from_chunks(self):
        resp = sse({'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'c1', 'function': {'name': 'read_file', 'arguments': '{"pa'}}]}}]},
                    {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': 'th":"a.py"}'}}]}}]})
        with mock.patch('urllib.request.urlopen', return_value=resp):
            r = lisicode.api_stream('k', {})
        tc = r['choices'][0]['message']['tool_calls'][0]
        self.assertEqual(tc['id'], 'c1')
        self.assertEqual(tc['function']['name'], 'read_file')
        self.assertEqual(json.loads(tc['function']['arguments']), {'path': 'a.py'})

    def test_gemini_style_calls_without_index(self):
        resp = sse({'choices': [{'delta': {'tool_calls': [{'id': '', 'function': {'name': 'list_files', 'arguments': '{}'}}]}}]},
                    {'choices': [{'delta': {'tool_calls': [{'id': '', 'function': {'name': 'read_file', 'arguments': '{"path":"x"}'}}]}}]})
        with mock.patch('urllib.request.urlopen', return_value=resp):
            r = lisicode.api_stream('k', {})
        tcs = r['choices'][0]['message']['tool_calls']
        self.assertEqual([t['function']['name'] for t in tcs], ['list_files', 'read_file'])
        self.assertTrue(all(t['id'] for t in tcs))

    def test_fallback_when_stream_rejected(self):
        err = urllib.error.HTTPError('u', 400, 'bad', {}, io.BytesIO(b'no stream'))
        with mock.patch('urllib.request.urlopen', side_effect=err), \
             mock.patch.object(lisicode, 'api_call', return_value={'choices': [{'message': {'content': 'ok'}}]}) as ac:
            r = lisicode.chat_request('k', {'model': 'm'})
        ac.assert_called_once()
        self.assertFalse(r['_streamed'])


class DiffAndInstructionTests(unittest.TestCase):
    def test_overwrite_shows_diff(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d).resolve(); (w / 'a.txt').write_text('one\ntwo\n', encoding='utf-8')
            buf = io.StringIO()
            with mock.patch.object(lisicode, 'confirm_action', return_value=True), mock.patch('sys.stdout', buf):
                lisicode.write_file(w, 'a.txt', 'one\nthree\n')
            out = buf.getvalue()
            self.assertIn('+three', out); self.assertIn('-two', out)
            self.assertEqual((w / 'a.txt').read_text(encoding='utf-8'), 'one\nthree\n')

    def test_overwrite_declined_keeps_file(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d).resolve(); (w / 'a.txt').write_text('old', encoding='utf-8')
            with mock.patch.object(lisicode, 'confirm_action', return_value=False), mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(lisicode.write_file(w, 'a.txt', 'new'), 'Перезапись отменена')
            self.assertEqual((w / 'a.txt').read_text(encoding='utf-8'), 'old')

    def test_new_file_preview(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d).resolve(); buf = io.StringIO()
            with mock.patch('sys.stdout', buf): lisicode.write_file(w, 'sub/n.txt', 'x\ny\n')
            self.assertIn('Новый файл', buf.getvalue()); self.assertTrue((w / 'sub' / 'n.txt').exists())

    def test_instructions_file(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d)
            self.assertEqual(lisicode.instructions_block(w), '')
            (w / 'LISICODE.md').write_text('Всегда отвечай кратко', encoding='utf-8')
            self.assertIn('Всегда отвечай кратко', lisicode.instructions_block(w))


class ProviderTests(unittest.TestCase):
    def tearDown(self): lisicode.set_provider('target')

    def test_gemini_models_prefix_and_filter(self):
        lisicode.set_provider('gemini')
        data = {'data': [{'id': 'models/gemini-2.5-flash'}, {'id': 'models/text-embedding-004'}]}
        with mock.patch.object(lisicode, 'api_call', return_value=data):
            self.assertEqual(lisicode.models_list('k'), ['gemini-2.5-flash'])

    def test_provider_urls(self):
        lisicode.set_provider('groq'); self.assertEqual(lisicode.API, 'https://api.groq.com/openai/v1')
        lisicode.set_provider('openrouter'); self.assertEqual(lisicode.API, 'https://openrouter.ai/api/v1')

    def test_old_config_key_migrates_to_target(self):
        cfg = {'api_key': 'sk-old-key-123456'}
        with mock.patch('builtins.input', return_value=''):
            self.assertEqual(lisicode.get_key(cfg), 'sk-old-key-123456')
        self.assertEqual(cfg['api_keys']['target'], 'sk-old-key-123456')
        self.assertEqual(lisicode.CURRENT_PROVIDER, 'target')


class KeyDetectionTests(unittest.TestCase):
    def test_target_models_fixed_list_without_network(self):
        lisicode.set_provider('target')
        with mock.patch.object(lisicode, 'api_call', side_effect=AssertionError('no network')):
            ms = lisicode.models_list('k')
        self.assertEqual(ms[0], 'claude-opus-5-5'); self.assertIn('gemini-4-argon', ms); self.assertEqual(len(ms), 10)

    def tearDown(self): lisicode.set_provider('target')

    def test_detect_provider_by_prefix(self):
        d = lisicode.detect_provider
        self.assertEqual(d('gkabc123'), 'target')
        self.assertEqual(d('gk-abc123'), 'target')
        self.assertEqual(d('gsk_abc'), 'groq')   # gsk_ — это Groq, не Target Shop
        self.assertIsNone(d('JKabc123'))
        self.assertEqual(d('sk-ant-api03-xyz'), 'anthropic')
        self.assertEqual(d('sk-or-v1-xyz'), 'openrouter')
        self.assertEqual(d('gsk_abc'), 'groq')
        self.assertEqual(d('xai-abc'), 'xai')
        self.assertEqual(d('AIzaSyABC'), 'gemini')
        self.assertEqual(d('sk-proj-abc'), 'openai')
        self.assertIsNone(d('something-else'))

    def test_new_gk_key_selects_target_and_saves(self):
        cfg = {}
        with mock.patch.object(lisicode, 'read_secret', return_value='gktest1234567'), \
             mock.patch.object(lisicode, 'api_call', return_value={'data': []}), \
             mock.patch.object(lisicode, 'save_cfg'), mock.patch('sys.stdout', io.StringIO()):
            k = lisicode.get_key(cfg)
        self.assertEqual(k, 'gktest1234567')
        self.assertEqual(cfg['provider'], 'target')
        self.assertEqual(cfg['api_keys']['target'], 'gktest1234567')
        self.assertEqual(lisicode.API, 'https://api.target-app.shop/v1')

    def test_openai_key_switches_url_and_unknown_key_asks(self):
        cfg = {}
        with mock.patch.object(lisicode, 'read_secret', return_value='sk-proj-abcdef123456'), \
             mock.patch.object(lisicode, 'api_call', return_value={'data': []}), \
             mock.patch.object(lisicode, 'save_cfg'), mock.patch('sys.stdout', io.StringIO()):
            lisicode.get_key(cfg)
        self.assertEqual(cfg['provider'], 'openai'); self.assertEqual(lisicode.API, 'https://api.openai.com/v1')
        cfg2 = {}
        with mock.patch.object(lisicode, 'read_secret', return_value='weirdkey123456'), \
             mock.patch('builtins.input', return_value='3'), \
             mock.patch.object(lisicode, 'api_call', return_value={'data': []}), \
             mock.patch.object(lisicode, 'save_cfg'), mock.patch('sys.stdout', io.StringIO()):
            lisicode.get_key(cfg2)
        self.assertEqual(cfg2['provider'], 'groq')

    def test_rejected_key_restores_previous_provider(self):
        lisicode.set_provider('target')
        with mock.patch.object(lisicode, 'read_secret', return_value='gsk_badkey123456'), \
             mock.patch.object(lisicode, 'api_call', side_effect=RuntimeError('HTTP 401: nope')), \
             mock.patch('sys.stdout', io.StringIO()):
            with self.assertRaises(RuntimeError): lisicode.get_key({})
        self.assertEqual(lisicode.CURRENT_PROVIDER, 'target')

    def test_models_endpoint_missing_is_only_warning(self):
        with mock.patch.object(lisicode, 'api_call', side_effect=RuntimeError('HTTP 404: no models')), mock.patch('sys.stdout', io.StringIO()):
            lisicode.verify_key('sk-ant-x')   # не должно падать

    def test_manual_model_when_list_unavailable(self):
        with mock.patch.object(lisicode, 'models_list', side_effect=RuntimeError('HTTP 404')), \
             mock.patch('builtins.input', return_value='claude-sonnet-5-5'), mock.patch('sys.stdout', io.StringIO()):
            self.assertEqual(lisicode.choose_model({}, 'k'), 'claude-sonnet-5-5')

    def test_manual_model_name_instead_of_number(self):
        with mock.patch.object(lisicode, 'models_list', return_value=['a', 'b']), \
             mock.patch('builtins.input', return_value='my-model-x'), mock.patch('sys.stdout', io.StringIO()):
            self.assertEqual(lisicode.choose_model({}, 'k'), 'my-model-x')

    def test_large_list_search_then_pick(self):
        ms = ['gpt-%d' % i for i in range(60)] + ['claude-x', 'claude-y']
        answers = iter(['claude', '2'])
        with mock.patch.object(lisicode, 'models_list', return_value=ms), \
             mock.patch('builtins.input', lambda *_: next(answers)), mock.patch('sys.stdout', io.StringIO()):
            self.assertEqual(lisicode.choose_model({}, 'k'), 'claude-y')


if __name__ == '__main__':
    unittest.main()
