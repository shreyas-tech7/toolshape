"""The run_code sandbox for shape C.

A script runs in a child Python process with:
- an AST check before it runs (import allowlist, no names or attributes that start with "_",
  no eval, exec, compile, getattr and friends),
- rlimits on CPU time and address space, plus a wall-clock timeout,
- an audit hook that blocks sockets to anything but the fake API, file opens outside the
  run's temp directory, new imports, subprocesses, os.system, exec and fork.

This guards the local benchmark only. It is not a security sandbox.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED_IMPORTS = ("json", "math", "datetime", "collections", "itertools", "re", "statistics", "functools")
FORBIDDEN_NAMES = frozenset({
    "eval", "exec", "compile", "getattr", "setattr", "delattr", "globals", "locals", "vars", "breakpoint",
    "input", "memoryview", "help", "exit", "quit", "type", "object", "super", "classmethod",
})
MAX_SCRIPT = 20_000
MAX_OUTPUT = 20_000
DEFAULT_TIMEOUT = 10.0
DEFAULT_MEMORY_MB = 512


class ScriptRejected(ValueError):
    pass


def check_script(code: str) -> None:
    """Raise ScriptRejected if the script breaks a syntax rule."""
    if len(code) > MAX_SCRIPT:
        raise ScriptRejected(f"script is longer than {MAX_SCRIPT} characters")
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise ScriptRejected(f"syntax error: {e.msg} (line {e.lineno})") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    raise ScriptRejected(f"import of {alias.name} is not allowed. Allowed: {', '.join(ALLOWED_IMPORTS)}")
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module not in ALLOWED_IMPORTS:
                raise ScriptRejected(f"import from {node.module} is not allowed. Allowed: {', '.join(ALLOWED_IMPORTS)}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ScriptRejected(f"attribute {node.attr} is not allowed (names that start with _ are blocked)")
        elif isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in FORBIDDEN_NAMES):
            raise ScriptRejected(f"name {node.id} is not allowed")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name.startswith("_"):
            raise ScriptRejected(f"name {node.name} is not allowed")
        elif isinstance(node, ast.arg) and node.arg.startswith("_"):
            raise ScriptRejected(f"name {node.arg} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ScriptRejected("global and nonlocal are not allowed")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            raise ScriptRejected("async code is not allowed")


# The child's bootstrap. It runs with `python -I` and receives its config as argv[1] (JSON).
BOOTSTRAP = r'''
import json, os, resource, sys
cfg = json.loads(sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU, (cfg["cpu"], cfg["cpu"]))
mem = cfg["mem_mb"] * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
os.chdir(cfg["tmp"])
sys.path.insert(0, cfg["pkg_path"])
import io, contextlib, traceback
import math, datetime, collections, itertools, re, statistics, functools, _strptime, encodings.idna
from toolcut.taskdesk.client import TaskDesk, TaskDeskError
code = sys.stdin.read()
TMP = os.path.realpath(cfg["tmp"])
API = (cfg["host"], cfg["port"])
ALLOWED_MODULES = set(cfg["allowed"])
BLOCK_PREFIX = ("subprocess.", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
                "pty.", "ctypes.", "os.kill", "os.putenv", "os.unsetenv", "shutil.", "os.remove", "os.rmdir",
                "os.rename", "os.unlink", "os.mkdir", "os.chmod", "os.chown", "os.link", "os.symlink", "webbrowser.")
_realpath = os.path.realpath
_fspath = os.fspath

def _hook(event, args):
    if event == "socket.connect":
        addr = args[1]
        if not (isinstance(addr, tuple) and tuple(addr[:2]) == API):
            raise PermissionError(f"network blocked: only the TaskDesk API at {API[0]}:{API[1]} is reachable")
    elif event in ("socket.sendto", "socket.sendmsg", "socket.bind"):
        raise PermissionError("network blocked: " + event)
    elif event == "socket.getaddrinfo":
        if args[0] not in (API[0], API[0].encode()):
            raise PermissionError(f"network blocked: lookup of {args[0]!r}")
    elif event == "open":
        path = args[0]
        if isinstance(path, int):
            return
        p = _realpath(_fspath(path))
        if isinstance(p, bytes):
            p = p.decode(errors="replace")
        if not (p == TMP or p.startswith(TMP + os.sep)):
            raise PermissionError(f"file access blocked outside the run's temp directory: {path!r}")
    elif event == "import":
        if args[0].split(".")[0] not in ALLOWED_MODULES:
            raise ImportError(f"import of {args[0]} is not allowed")
    elif event.startswith(BLOCK_PREFIX):
        raise PermissionError(f"blocked: {event}")

taskdesk = TaskDesk(f"http://{API[0]}:{API[1]}")
env = {"taskdesk": taskdesk, "TaskDeskError": TaskDeskError, "__name__": "__run_code__"}
compiled = compile(code, "<run_code>", "exec")
out = io.StringIO()
real_stdout = sys.stdout
sys.addaudithook(_hook)
error = None
try:
    with contextlib.redirect_stdout(out):
        exec(compiled, env)
except BaseException as e:
    tb = traceback.extract_tb(e.__traceback__)
    line = next((f.lineno for f in reversed(tb) if f.filename == "<run_code>"), None)
    error = f"{type(e).__name__}: {e}" + (f" (script line {line})" if line else "")
real_stdout.write(json.dumps({"stdout": out.getvalue(), "error": error}))
'''


@dataclass
class RunResult:
    stdout: str
    error: str | None
    timed_out: bool = False

    def as_text(self) -> str:
        text = self.stdout
        if len(text) > MAX_OUTPUT:
            text = text[:MAX_OUTPUT] + f"\n[output cut at {MAX_OUTPUT} characters]"
        if self.error:
            text += ("\n" if text else "") + "Error: " + self.error
        return text or "(no output)"


def run_code(code: str, api_url: str, *, timeout: float = DEFAULT_TIMEOUT, memory_mb: int = DEFAULT_MEMORY_MB,
             skip_ast_check: bool = False) -> RunResult:
    """Run a script against the TaskDesk API in a limited child process.

    skip_ast_check exists only so tests can prove that the audit hook holds on its own.
    """
    if not skip_ast_check:
        try:
            check_script(code)
        except ScriptRejected as e:
            return RunResult("", f"ScriptRejected: {e}")
    url = urlsplit(api_url)
    pkg_path = str(Path(__file__).resolve().parent.parent)
    with tempfile.TemporaryDirectory(prefix="toolcut-run-") as tmp:
        cfg = {"cpu": max(1, int(timeout) + 1), "mem_mb": memory_mb, "tmp": tmp, "pkg_path": pkg_path,
               "host": url.hostname, "port": url.port, "allowed": list(ALLOWED_IMPORTS) + ["encodings"]}
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
                [sys.executable, "-I", "-c", BOOTSTRAP, json.dumps(cfg)],
                input=code, capture_output=True, text=True, timeout=timeout, cwd=tmp,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            )
        except subprocess.TimeoutExpired:
            return RunResult("", f"TimeoutError: the script ran longer than {timeout:g} seconds and was stopped", timed_out=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
        if proc.returncode in (-9, -24):  # SIGKILL or SIGXCPU from the CPU limit
            return RunResult("", "TimeoutError: the script hit the CPU time limit and was stopped", timed_out=True)
        return RunResult("", f"SandboxError: {tail[0]}")
    return RunResult(payload.get("stdout", ""), payload.get("error"))
