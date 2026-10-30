import collections
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import alerts


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.events = []
        self.patches = [patch.object(alerts, name, value) for name, value in {
            'BASE': self.folder, 'QUEUE': self.folder / 'queue',
            'HISTORY': self.folder / 'history.jsonl', 'STATUS': self.folder / 'status.json',
            'CODEX': self.folder / 'codex',
        }.items()]
        for item in self.patches:
            item.start()
        alerts.QUEUE.mkdir()
        self.reader = alerts.TranscriptReader(lambda *a, **kw: self.events.append((a, kw)),
                                              started=time.time()-1)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def row(self, kind, payload):
        return json.dumps({'type': kind, 'payload': payload,
                           'timestamp': dt.datetime.now(dt.timezone.utc).isoformat()}).encode()+b'\n'

    def session(self, name, date='2026/01/02'):
        path = alerts.CODEX / 'sessions' / date / (name+'.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.row('session_meta', {'id': name, 'cwd': 'X:/example'}))
        return path

    def append(self, path, data):
        with path.open('ab') as stream:
            stream.write(data)

    def app(self):
        app = alerts.AlertsApp.__new__(alerts.AlertsApp)
        app.events = collections.deque()
        app.seen = collections.OrderedDict()
        app.loaded = set()
        app.last_heartbeat = time.time()
        app.last_sound = time.time()
        app.stopping = False
        app.root = types.SimpleNamespace(after=lambda *a: None, withdraw=lambda: None)
        app.show = lambda: None
        return app

    def test_existing_new_and_resumed_older_chat(self):
        a, b = self.session('A'), self.session('B', '2025/12/01')
        self.append(a, self.row('event_msg', {'type':'task_complete','turn_id':'old'}))
        self.reader.discover(initial=True)
        self.append(a, self.row('event_msg', {'type':'task_complete','turn_id':'A-1'}))
        self.append(b, self.row('event_msg', {'type':'task_complete','turn_id':'B-1'}))
        c = self.session('C')
        self.append(c, self.row('event_msg', {'type':'task_complete','turn_id':'C-1'}))
        self.reader.discover()
        self.reader.poll()
        self.reader.poll()
        self.assertEqual({event[0][2] for event in self.events}, {'A-1','B-1','C-1'})
        self.assertEqual(len(self.events), 3)
        self.assertTrue(all(event[0][3] == 'X:/example' for event in self.events))

    def test_partial_write_and_unicode(self):
        path = self.session('A')
        self.reader.discover(initial=True)
        row = self.row('event_msg', {'type':'task_complete','turn_id':'中文'})
        self.append(path, row[:20])
        self.reader.poll()
        self.assertEqual(self.events, [])
        self.append(path, row[20:])
        self.reader.poll()
        self.assertEqual(self.events[0][0][2], '中文')

    def test_subagent_does_not_alert(self):
        state = {'session':'sub','turn':'','cwd':''}
        self.reader.line(self.row('session_meta', {'source':{'subagent':{}}}), state)
        self.reader.line(self.row('event_msg', {'type':'task_complete'}), state)
        self.assertEqual(self.events, [])

    def test_malformed_records_do_not_stop_reader(self):
        state = {'session':'A','turn':'','cwd':''}
        for raw in (b'garbage', b'[]', b'null', b'{"payload":[]}',
                    b'{"timestamp":null}', b'{"timestamp":42}'):
            self.reader.line(raw, state)
        self.assertEqual(self.events, [])

    def test_questions_and_error_retry(self):
        state = {'session':'A','turn':'1','cwd':''}
        self.reader.line(self.row('response_item', {'type':'function_call','name':'request_user_input','call_id':'c1'}), state)
        self.reader.line(self.row('event_msg', {'type':'error','will_retry':True}), state)
        self.reader.line(self.row('event_msg', {'type':'error','will_retry':False}), state)
        self.assertEqual([event[0][0] for event in self.events], ['question','error'])
        self.assertEqual(self.events[0][1]['key'], 'question|A|1|c1')

    def test_hooks_emit_without_persisting_content(self):
        with patch.object(alerts, 'ensure_daemon'):
            for event, name in [('PermissionRequest','Bash'), ('PreToolUse','request_user_input'), ('Stop','')]:
                alerts.hook({'hook_event_name':event,'tool_name':name,'session_id':'A',
                             'turn_id':'1','tool_input':{'secret':'DO_NOT_PERSIST'}})
        raw = '\n'.join(path.read_text() for path in alerts.QUEUE.glob('*.json'))
        self.assertNotIn('DO_NOT_PERSIST', raw)
        self.assertEqual(len(list(alerts.QUEUE.glob('*.json'))), 3)

    def test_paused_and_disabled_hooks_do_not_restart(self):
        for marker in ('paused','disabled'):
            (self.folder / marker).touch()
            with patch.object(alerts, 'ensure_daemon') as start:
                alerts.hook({'hook_event_name':'Stop'})
                start.assert_not_called()
            (self.folder / marker).unlink()
        self.assertEqual(list(alerts.QUEUE.glob('*.json')), [])

    def test_old_pending_survives_restart_and_is_acknowledged(self):
        alerts.enqueue('approval', 'A', '1', timestamp=time.time()-3600)
        app = self.app()
        app.tick()
        self.assertEqual(len(app.events), 1)
        self.assertEqual(len(list(alerts.QUEUE.glob('*.json'))), 1)
        restarted = self.app()
        restarted.tick()
        self.assertEqual(len(restarted.events), 1)
        restarted.dismiss()
        self.assertEqual(list(alerts.QUEUE.glob('*.json')), [])

    def test_chronological_order_and_duplicate_completion(self):
        alerts.enqueue('complete','A','1',timestamp=time.time())
        alerts.enqueue('complete','A','1',source='transcript',timestamp=time.time())
        alerts.enqueue('question','B','2',timestamp=time.time()-10)
        app = self.app()
        app.tick()
        self.assertEqual([event['kind'] for event, _ in app.events], ['question','complete'])
        self.assertEqual(len(list(alerts.QUEUE.glob('*.json'))), 2)
        app.tick()
        self.assertEqual(len(app.events), 2)
        app.dismiss_all()
        self.assertEqual(list(alerts.QUEUE.glob('*.json')), [])

    def test_corrupt_queue_is_quarantined(self):
        path = alerts.QUEUE / 'broken.json'
        path.write_text('[]')
        self.app().tick()
        self.assertTrue(path.with_suffix('.invalid').exists())

    def test_invalid_queue_metadata_and_timestamp(self):
        alerts.enqueue('complete','A','1')
        path = next(alerts.QUEUE.glob('*.json'))
        value = json.loads(path.read_text())
        value['time'] = float('inf')
        self.assertFalse(alerts.valid_event(value))
        value['time'] = time.time()
        value.pop('session')
        self.assertFalse(alerts.valid_event(value))

    def test_oversized_record_does_not_grow_buffer_or_hide_next_event(self):
        path = self.session('A')
        self.reader.discover(initial=True)
        with patch.object(alerts, 'MAX_LINE_BYTES', 256):
            self.append(path, b'x' * 300)
            self.reader.poll()
            self.assertEqual(self.reader.states[path]['partial'], b'')
            self.append(path, b'x\n' + self.row('event_msg', {'type':'task_complete','turn_id':'next'}))
            self.reader.poll()
        self.assertEqual(self.events[0][0][2], 'next')

    def test_history_rotates(self):
        alerts.HISTORY.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
        alerts.append_history({'kind':'test'})
        self.assertTrue(alerts.HISTORY.with_suffix('.jsonl.1').exists())
        self.assertEqual(json.loads(alerts.HISTORY.read_text())['kind'], 'test')


if __name__ == '__main__':
    unittest.main()
