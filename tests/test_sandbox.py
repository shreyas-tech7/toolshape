"""run_code sandbox limits. Each test names the broken case it guards against."""

import os

import pytest

from toolcut.sandbox import ScriptRejected, check_script, run_code


def test_reaches_the_fake_api(api):
    r = run_code("print(taskdesk.get_task(task_id=1)['id'])", api.url)
    assert r.error is None and r.stdout.strip() == "1"


def test_network_other_hosts_blocked_by_client_redirect(api):
    """Broken case: a script points the client at another host and connects out."""
    code = "taskdesk.base_url = 'http://10.1.2.3:80'\nprint(taskdesk.get_task(task_id=1)['id'])"
    r = run_code(code, api.url, timeout=5)  # the script's taskdesk holds only the ops, so this changes nothing
    assert r.error is None and r.stdout.strip() == "1"
    r = run_code(code, api.url, timeout=5, skip_ast_check=True)  # the real client, with only the audit hook
    assert r.error and "network blocked" in r.error


def test_network_raw_socket_blocked_even_without_the_ast_check(api):
    """Broken case: the audit hook alone must stop a socket to anything but the fake API."""
    code = "import socket\ns = socket.socket()\ns.connect(('10.1.2.3', 80))"
    r = run_code(code, api.url, skip_ast_check=True, timeout=5)
    assert r.error and "network blocked: only the TaskDesk API" in r.error
    code = "import socket\ns = socket.socket()\ns.connect(('127.0.0.1', 9))"  # local, but not the API port
    r = run_code(code, api.url, skip_ast_check=True, timeout=5)
    assert r.error and "network blocked" in r.error
    code = "import socket\ns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\ns.sendto(b'x', ('10.1.2.3', 53))"
    r = run_code(code, api.url, skip_ast_check=True, timeout=5)
    assert r.error and "network blocked" in r.error


def test_files_outside_temp_dir_blocked(api, tmp_path):
    """Broken case: a script reads a file outside its own temp directory."""
    secret = tmp_path / "secret.txt"
    secret.write_text("do not read")
    r = run_code(f"print(open({str(secret)!r}).read())", api.url)
    assert r.error and "file access blocked" in r.error and "do not read" not in r.stdout
    r = run_code("print(open('/etc/passwd').read())", api.url)
    assert r.error and "file access blocked" in r.error
    r = run_code("print(open('../../etc/passwd').read())", api.url)
    assert r.error and "file access blocked" in r.error


def test_files_inside_temp_dir_allowed(api):
    r = run_code("f = open('note.txt', 'w')\nf.write('hi')\nf.close()\nprint(open('note.txt').read())", api.url)
    assert r.error is None and r.stdout.strip() == "hi"


def test_time_limit_stops_a_loop(api):
    """Broken case: an endless loop that never returns."""
    r = run_code("while True:\n    pass", api.url, timeout=2)
    assert r.timed_out and "TimeoutError" in r.error


def test_time_limit_stops_a_sleep(api):
    """Broken case: a script that waits without using CPU (only the wall clock catches it)."""
    r = run_code("import time\ntime.sleep(30)", api.url, timeout=2, skip_ast_check=True)
    assert r.timed_out


def test_memory_limit(api):
    """Broken case: a script allocates far more memory than the limit."""
    r = run_code("x = 'a' * (2 * 10**9)", api.url, memory_mb=512)
    assert r.error and "MemoryError" in r.error


def test_subprocess_and_os_system_blocked_without_the_ast_check(api):
    """Broken case: the audit hook alone must stop process creation."""
    r = run_code("import os\nos.system('echo hi')", api.url, skip_ast_check=True)
    assert r.error and "blocked: os.system" in r.error
    r = run_code("import subprocess", api.url, skip_ast_check=True)
    assert r.error and "not allowed" in r.error
    r = run_code("import os\nos.execv('/bin/echo', ['echo'])", api.url, skip_ast_check=True)
    assert r.error and "blocked: os.exec" in r.error


def test_child_sees_no_parent_secrets(api, monkeypatch):
    """Broken case: the child inherits a provider key from the parent environment."""
    monkeypatch.setenv("GROQ_API_KEY", "should-not-leak")
    r = run_code("import os\nprint(os.environ.get('GROQ_API_KEY'))", api.url, skip_ast_check=True)
    assert r.stdout.strip() == "None"
    assert os.environ["GROQ_API_KEY"] == "should-not-leak"


@pytest.mark.parametrize("code,word", [
    ("import os", "import of os"),
    ("from subprocess import run", "import from subprocess"),
    ("x = ().__class__", "__class__"),
    ("eval('1')", "eval"),
    ("exec('1')", "exec"),
    ("compile('1', 'x', 'exec')", "compile"),
    ("getattr(taskdesk, 'base_url')", "getattr"),
    ("taskdesk._call", "_call"),
    ("__import__('os')", "__import__"),
    ("def _f():\n    pass", "_f"),
    ("from .x import y", "import from"),
    ("x = (", "syntax error"),
])
def test_ast_rules_reject(code, word):
    with pytest.raises(ScriptRejected, match=word.replace("(", r"\(").replace(".", r"\.")):
        check_script(code)


def test_ast_allows_plain_code():
    check_script("import json\nfrom collections import Counter\nprint(json.dumps(Counter('aab')))")


def test_rejected_script_does_not_run(api):
    r = run_code("import os\nprint('ran')", api.url)
    assert r.error.startswith("ScriptRejected") and r.stdout == ""


# Probes from the outside check. Each one got past the sandbox before the fix.

@pytest.mark.parametrize("code,word", [
    ("import statistics\nm = statistics.sys.modules['__main__']", "modules"),
    ("def g():\n    yield 1\nx = g()\nprint(x.gi_frame)", "gi_frame"),
    ("print('{0.get_task}'.format(taskdesk))", "format"),
    ("print('{x}'.format_map({'x': 1}))", "format_map"),
    ("try:\n    1/0\nexcept Exception as e:\n    print(e.with_traceback(None))", "with_traceback"),
    ("match 'a':\n    case str(__class__=c):\n        print(c)", "__class__"),
])
def test_escape_probes_are_rejected_by_the_ast_check(code, word):
    with pytest.raises(ScriptRejected, match=word):
        check_script(code)


def test_allowed_modules_expose_no_submodules(api):
    """Broken case: statistics.sys reached the real sys module and through it __main__."""
    code = "import statistics, json, re, datetime\nprint(hasattr(statistics, 'sys'), hasattr(json, 'decoder'), hasattr(re, 'enum'), hasattr(datetime, 'sys'))"
    r = run_code(code, api.url)
    assert r.error is None and r.stdout.split() == ["False"] * 4


def test_taskdesk_holds_only_the_operations(api):
    r = run_code("print(hasattr(taskdesk, 'call'), hasattr(taskdesk, 'base_url'), hasattr(taskdesk, 'get_task'))", api.url)
    assert r.error is None and r.stdout.split() == ["False", "False", "True"]


def test_hook_settings_are_not_in_main_globals(api):
    """Broken case: a script rewrote TMP or API in __main__ and the hook read the new value."""
    code = "import sys\nm = sys.modules['__main__']\nprint([n for n in ('TMP', 'API', 'ALLOWED_MODULES', 'BLOCK_PREFIX', 'hook', 'cfg') if hasattr(m, n)])"
    r = run_code(code, api.url, skip_ast_check=True)
    assert r.error is None and r.stdout.strip() == "[]"


def test_os_is_not_reachable_through_an_allowed_module(api):
    """Broken case: a script reached os or sys through a module it was allowed to import."""
    code = "import datetime, functools, itertools, collections, math\nprint([hasattr(m, 'os') or hasattr(m, 'sys') for m in (datetime, functools, itertools, collections, math)])"
    r = run_code(code, api.url)
    assert r.error is None and "True" not in r.stdout


def test_proc_files_blocked(api):
    """Broken case: the script read the parent's environment through /proc."""
    for path in ("/proc/self/environ", f"/proc/{os.getpid()}/environ", "/etc/hostname"):
        r = run_code(f"print(open({path!r}).read())", api.url)
        assert r.error and "file access blocked" in r.error, path
