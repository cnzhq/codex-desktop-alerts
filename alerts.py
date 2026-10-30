"""Local-only, cross-conversation Codex desktop alerts. Python stdlib only."""
import argparse
import collections
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

VERSION = '0.1.0a1'
APP_PATH = Path(__file__).resolve()
DEFAULT_BASE = (APP_PATH.parent if (APP_PATH.parent / 'manifest.json').exists() else
                Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CodexDesktopAlerts')
BASE = Path(os.environ.get('CODEX_ALERTS_HOME', str(DEFAULT_BASE)))
QUEUE = BASE / 'queue'
HISTORY = BASE / 'history.jsonl'
STATUS = BASE / 'status.json'
try:
    SETTINGS = json.loads((BASE / 'settings.json').read_text(encoding='utf-8'))
except (OSError, ValueError):
    SETTINGS = {}
CODEX = Path(SETTINGS.get('codex_home') or os.environ.get('CODEX_HOME') or Path.home() / '.codex')
MUTEX_NAME = 'Local\\CodexDesktopAlerts-' + hashlib.sha256(str(BASE).lower().encode()).hexdigest()[:16]
TITLES = {'complete': 'Codex 本轮工作已结束', 'approval': 'Codex 需要你批准操作',
          'question': 'Codex 有问题需要你回答', 'error': 'Codex 运行遇到问题',
          'test': 'Codex 桌面提醒测试', 'panel': 'Codex 提醒中心'}
MAX_LINE_BYTES = 8 * 1024 * 1024


def valid_event(event):
    if not isinstance(event, dict) or event.get('kind') not in TITLES:
        return False
    if not all(isinstance(event.get(field), str) for field in
               ('session', 'turn', 'cwd', 'source', 'key')):
        return False
    if not isinstance(event.get('time'), (int, float)):
        return False
    try:
        dt.datetime.fromtimestamp(event['time'])
    except (OSError, ValueError, OverflowError):
        return False
    return True


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)


def process_running():
    try:
        data = json.loads(STATUS.read_text(encoding='utf-8'))
        return time.time() - data['heartbeat'] < 12
    except (OSError, ValueError, KeyError):
        return False


def ensure_daemon(resume=False):
    if (BASE / 'disabled').exists():
        return
    if resume:
        (BASE / 'paused').unlink(missing_ok=True)
    elif (BASE / 'paused').exists():
        return
    if process_running():
        return
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    subprocess.Popen([str(pythonw), str(APP_PATH), '--daemon'],
                     cwd=str(BASE), creationflags=0x08000000,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def enqueue(kind, session='', turn='', cwd='', source='hook', key='', timestamp=None):
    # Never persist prompts, tool arguments, model responses or credentials.
    event = {'kind': kind, 'session': session, 'turn': turn, 'cwd': cwd,
             'source': source, 'time': timestamp or time.time()}
    event['key'] = key or hashlib.sha256(
        f'{kind}|{session}|{turn}'.encode()).hexdigest()
    atomic_json(QUEUE / (uuid.uuid4().hex + '.json'), event)


def hook(payload):
    if not isinstance(payload, dict) or (BASE / 'disabled').exists() or (BASE / 'paused').exists():
        return
    event = payload.get('hook_event_name')
    kind = None
    if event == 'Stop':
        if not payload.get('stop_hook_active'):
            kind = 'complete'
    elif event == 'PermissionRequest':
        kind = 'approval'
    elif event == 'PreToolUse':
        name = payload.get('tool_name', '').lower()
        if any(term in name for term in ('request_user_input', 'requestuserinput', 'elicitation')):
            kind = 'question'
    if kind:
        session = payload.get('session_id', '')
        turn = payload.get('turn_id', '')
        key = ''
        if kind != 'complete':
            key = hashlib.sha256(json.dumps(
                [kind, session, turn, payload.get('tool_name'),
                 payload.get('tool_use_id'), payload.get('tool_input')],
                sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if kind == 'question' and payload.get('tool_use_id'):
            key = f"question|{session}|{turn}|{payload['tool_use_id']}"
        enqueue(kind, session, turn, payload.get('cwd', ''), key=key)
        ensure_daemon()


class TranscriptReader:
    """Fallback for completions, independent of hook loading/trust and conversation IDs."""
    def __init__(self, emit=enqueue, started=None):
        self.emit = emit
        self.started = started or time.time()
        self.states = {}
        self.last_scan = 0
        self.errors = 0

    def discover(self, initial=False):
        # All dates are intentional: resuming yesterday's chat appends to yesterday's file.
        found = set()
        for path in (CODEX / 'sessions').rglob('*.jsonl'):
            try:
                size = path.stat().st_size
            except OSError:
                self.errors += 1
                continue
            found.add(path)
            if path not in self.states:
                self.states[path] = {'offset': size if initial else 0,
                                     'partial': b'', 'session': path.stem[-36:],
                                     'turn': '', 'cwd': ''}
        for path in set(self.states) - found:
            self.states.pop(path)
        self.last_scan = time.monotonic()

    def line(self, raw, state):
        try:
            entry = json.loads(raw)
        except (ValueError, UnicodeError):
            return
        if not isinstance(entry, dict):
            return
        payload = entry.get('payload') or {}
        if not isinstance(payload, dict):
            return
        if entry.get('type') == 'session_meta':
            state['session'] = payload.get('id', state['session'])
            state['cwd'] = payload.get('cwd', '')
            state['subagent'] = isinstance(payload.get('source'), dict) and 'subagent' in payload['source']
        if entry.get('type') == 'turn_context':
            state['cwd'] = payload.get('cwd', state['cwd'])
            state['turn'] = payload.get('turn_id', state['turn'])
        if entry.get('type') == 'event_msg' and payload.get('type') == 'task_started':
            state['turn'] = payload.get('turn_id', state['turn'])
        try:
            stamp = dt.datetime.fromisoformat(entry.get('timestamp', '').replace('Z', '+00:00')).timestamp()
        except (ValueError, TypeError, AttributeError, OverflowError, OSError):
            return
        if stamp < self.started or state.get('subagent'):
            return
        kind = None
        if entry.get('type') == 'event_msg':
            if payload.get('type') == 'task_complete':
                kind = 'complete'
            elif payload.get('type') == 'error' and payload.get('will_retry') is False:
                kind = 'error'
        elif entry.get('type') == 'response_item' and payload.get('type') == 'function_call':
            name = payload.get('name', '').lower()
            if 'request_user_input' in name or 'requestuserinput' in name:
                kind = 'question'
        if kind:
            extra = {}
            if kind == 'question' and payload.get('call_id'):
                extra['key'] = f"question|{state['session']}|{state['turn']}|{payload['call_id']}"
            self.emit(kind, state['session'], payload.get('turn_id', state['turn']),
                      state['cwd'], source='transcript', timestamp=stamp, **extra)

    def poll(self):
        if time.monotonic() - self.last_scan > 3:
            self.discover()
        for path, state in list(self.states.items()):
            try:
                size = path.stat().st_size
                if size < state['offset']:
                    state['offset'], state['partial'] = 0, b''
                    state['skipping_line'] = False
                if size == state['offset']:
                    continue
                with path.open('rb') as stream:
                    # Recover just the metadata for existing conversations without replaying history.
                    if not state.get('cwd'):
                        self.line(stream.readline(MAX_LINE_BYTES + 1), state)
                    stream.seek(state['offset'])
                    chunk = stream.read(4 * 1024 * 1024)
                    state['offset'] = stream.tell()
                if state.get('skipping_line'):
                    _, separator, chunk = chunk.partition(b'\n')
                    if not separator:
                        continue
                    state['skipping_line'] = False
                lines = (state['partial'] + chunk).split(b'\n')
                state['partial'] = lines.pop()
                if len(state['partial']) > MAX_LINE_BYTES:
                    state['partial'] = b''
                    state['skipping_line'] = True
                for line in lines:
                    if len(line) <= MAX_LINE_BYTES:
                        self.line(line, state)
            except OSError:
                self.errors += 1


class AlertsApp:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('Codex 桌面提醒')
        self.root.attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self.dismiss)
        self.events = collections.deque()
        self.seen = collections.OrderedDict()
        self.loaded = set()
        self.reader = TranscriptReader()
        self.reader.discover(initial=True)
        self.last_heartbeat = 0
        self.last_sound = 0
        self.worker_error = ''
        self.stopping = False
        self.head = tk.StringVar()
        self.body = tk.StringVar()
        self.count = tk.StringVar()
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, textvariable=self.head, font=('Microsoft YaHei UI', 14, 'bold'),
                  wraplength=420).pack(anchor='w', pady=(0, 12))
        ttk.Label(frame, textvariable=self.body, font=('Microsoft YaHei UI', 10),
                  wraplength=420, justify='left').pack(anchor='w')
        ttk.Label(frame, textvariable=self.count).pack(anchor='w', pady=(12, 8))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='回到 VS Code', command=self.open_vscode).pack(side='left')
        ttk.Button(buttons, text='知道了', command=self.dismiss).pack(side='right')
        ttk.Button(buttons, text='全部已读', command=self.dismiss_all).pack(side='right', padx=6)
        ttk.Label(frame, text='弹窗保留到手动关闭；关闭弹窗后仍继续监听。',
                  foreground='#666666').pack(anchor='w', pady=(12, 0))
        threading.Thread(target=self.watch, daemon=True).start()
        self.root.after(300, self.tick)

    def watch(self):
        while not self.stopping:
            try:
                self.reader.poll()
                self.worker_error = ''
            except Exception as exc:
                self.worker_error = type(exc).__name__
            time.sleep(1)

    def tick(self):
        try:
            if (BASE / 'stop.request').exists():
                (BASE / 'stop.request').unlink(missing_ok=True)
                self.stopping = True
                self.root.destroy()
                return
            now = time.time()
            if now - self.last_heartbeat > 3:
                atomic_json(STATUS, {'pid': os.getpid(), 'heartbeat': now,
                                     'started': self.reader.started,
                                     'watched_files': len(self.reader.states),
                                     'watcher_error': self.worker_error, 'version': VERSION,
                                     'read_errors': self.reader.errors,
                                     'codex_home': str(CODEX),
                                     'window_visible': bool(self.root.winfo_viewable()),
                                     'pending_alerts': len(self.events),
                                     'displayed_title': self.head.get()})
                self.last_heartbeat = now
            arrivals = []
            for path in QUEUE.glob('*.json'):
                if path in self.loaded:
                    continue
                try:
                    event = json.loads(path.read_text(encoding='utf-8'))
                    if not valid_event(event):
                        raise ValueError('invalid event')
                    arrivals.append((event, path))
                except ValueError:
                    path.replace(path.with_suffix('.invalid'))
                except OSError:
                    continue
            for event, path in sorted(arrivals, key=lambda pair: (pair[0]['time'], pair[1].name)):
                try:
                    key = event['key']
                    # Hooks and transcript fallback must produce just one completion alert.
                    if key in self.seen:
                        path.unlink(missing_ok=True)
                        continue
                    self.seen[key] = now
                    while len(self.seen) > 2000:
                        self.seen.popitem(last=False)
                    self.loaded.add(path)
                    self.events.append((event, path))
                    try:
                        append_history(event)
                    except OSError:
                        self.worker_error = 'HistoryWriteError'
                    self.show()
                    if now - self.last_sound > 5:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                        self.last_sound = now
                except (OSError, ValueError, KeyError):
                    continue
        finally:
            if not self.stopping:
                self.root.after(500, self.tick)

    def show(self):
        if not self.events:
            self.root.withdraw()
            return
        item = self.events[0][0]
        self.head.set(TITLES.get(item['kind'], 'Codex 提醒'))
        workspace = Path(item['cwd']).name if item['cwd'] else 'Codex 对话'
        session = item['session'][-8:] or '测试'
        clock = dt.datetime.fromtimestamp(item['time']).strftime('%H:%M:%S')
        self.body.set(f'项目：{workspace}\n对话：…{session}    时间：{clock}\n\n'
                      + ('请返回 VS Code 查看结果或继续对话。' if item['kind'] == 'complete'
                         else '请返回 VS Code 查看并处理。'))
        self.count.set(f'未读提醒：{len(self.events)} 条')
        self.root.update_idletasks()
        width, height = 480, max(260, self.root.winfo_reqheight())
        rect = (ctypes.c_long * 4)()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, rect, 0)
        self.root.geometry(f'{width}x{height}+{max(rect[0], rect[2]-width-20)}+{max(rect[1], rect[3]-height-20)}')
        self.root.deiconify()
        self.root.attributes('-topmost', True)

    def dismiss(self):
        if self.events:
            _, path = self.events.popleft()
            path.unlink(missing_ok=True)
            self.loaded.discard(path)
        self.show()

    def dismiss_all(self):
        for _, path in self.events:
            path.unlink(missing_ok=True)
            self.loaded.discard(path)
        self.events.clear()
        self.root.withdraw()

    def open_vscode(self):
        # Activate an existing VS Code window; never send input or approve anything.
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        @callback_type
        def visit(hwnd, unused):
            title = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(hwnd, title, 1024)
            if user32.IsWindowVisible(hwnd) and 'Visual Studio Code' in title.value:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return False
            return True
        user32.EnumWindows(visit, 0)

    def run(self):
        self.root.mainloop()


def daemon():
    if (BASE / 'disabled').exists():
        return
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(mutex)
        return
    try:
        QUEUE.mkdir(parents=True, exist_ok=True)
        (BASE / 'stop.request').unlink(missing_ok=True)
        (BASE / 'paused').unlink(missing_ok=True)
        AlertsApp().run()
    finally:
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(mutex)
        try:
            data = json.loads(STATUS.read_text(encoding='utf-8'))
            if data.get('pid') == os.getpid():
                STATUS.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=VERSION)
    actions = parser.add_mutually_exclusive_group()
    for option in ('daemon', 'hook', 'test', 'status', 'stop', 'panel'):
        actions.add_argument('--' + option, action='store_true')
    args = parser.parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    if args.hook:
        try:
            hook(json.load(sys.stdin))
        except Exception as exc:
            # Notification failures must never alter tool approval or block Codex.
            record_error(type(exc).__name__)
        print('{}')
    elif args.daemon:
        if sys.platform != 'win32':
            parser.error('Desktop notifications require Windows.')
        daemon()
    elif args.status:
        print(json.dumps({'running': process_running(), 'location': str(BASE),
                          'status': json.loads(STATUS.read_text(encoding='utf-8'))
                          if STATUS.exists() else None}, ensure_ascii=False, indent=2))
    elif args.stop:
        (BASE / 'paused').touch()
        (BASE / 'stop.request').touch()
    else:
        if sys.platform != 'win32':
            parser.error('Desktop notifications require Windows.')
        ensure_daemon(resume=True)
        enqueue('test' if args.test else 'panel', key=str(uuid.uuid4()))


def append_history(event):
    # At most four files of roughly 2 MiB; queue files remain until acknowledged.
    if HISTORY.exists() and HISTORY.stat().st_size > 2 * 1024 * 1024:
        for index in (3, 2, 1):
            previous = HISTORY if index == 1 else HISTORY.with_suffix(f'.jsonl.{index-1}')
            if previous.exists():
                os.replace(previous, HISTORY.with_suffix(f'.jsonl.{index}'))
    with HISTORY.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')


def record_error(error_type):
    # Only exception class and time: exception messages may contain private input.
    with (BASE / 'errors.log').open('a', encoding='utf-8') as stream:
        stream.write(f'{dt.datetime.now(dt.timezone.utc).isoformat()} {error_type}\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        record_error(sys.exc_info()[0].__name__)
        if sys.stdout is not None:
            raise
