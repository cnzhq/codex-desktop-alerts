"""Pure hook transforms. Never remove an entire group containing another handler."""
from copy import deepcopy
from pathlib import Path

MARKER = 'Codex Desktop Alerts [v1]'
LEGACY_MARKER = 'Codex desktop alert'
EVENTS = ('Stop', 'PermissionRequest', 'PreToolUse')


def command_for(python_exe, app_path):
    for value in (str(python_exe), str(app_path)):
        if any(char in value for char in ('"', '\r', '\n', '%', '!', '&', '|', '<', '>', '^', '`', '$')):
            raise ValueError('Unsupported shell metacharacter in install or Python path')
    return f'"{python_exe}" "{app_path}" --hook'


def owned(handler, app_path):
    if not isinstance(handler, dict):
        return False
    command = handler.get('command', '')
    # Both exact marker and exact quoted script path are required.
    return (handler.get('statusMessage') in (MARKER, LEGACY_MARKER)
            and isinstance(command, str)
            and f'"{app_path}" --hook'.casefold() in command.casefold())


def remove(config, app_path):
    result = deepcopy(config)
    hooks = result.get('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('hooks must be an object')
    for event in EVENTS:
        if event not in hooks:
            continue
        groups = hooks[event]
        if not isinstance(groups, list):
            raise ValueError(f'{event} must be an array')
        remaining = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError(f'Invalid {event} matcher group')
            kept = [handler for handler in group['hooks'] if not owned(handler, app_path)]
            if kept:
                remaining.append({**group, 'hooks': kept})
        if remaining:
            hooks[event] = remaining
        else:
            hooks.pop(event)
    return result


def install(config, python_exe, app_path):
    result = remove(config, app_path)
    hooks = result.setdefault('hooks', {})
    command = command_for(python_exe, app_path)
    for event in EVENTS:
        handler = {'type': 'command', 'command': command,
                   'timeout': 5, 'statusMessage': MARKER}
        group = {'hooks': [handler]}
        if event == 'PreToolUse':
            group['matcher'] = 'request_user_input|requestUserInput|elicitation'
        hooks.setdefault(event, []).append(group)
    return result
