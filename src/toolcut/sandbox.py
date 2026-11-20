"""The run_code sandbox for shape C.

A script runs in a child Python process with:
- an AST check before it runs (import allowlist, no names or attributes that start with "_",
  no frame, code or traceback attributes, no str.format, no eval, exec, compile, getattr and friends),
- restricted builtins whose __import__ hands out proxies of the allowed modules (public names
  only, no submodules), and a taskdesk object that holds only the API operations,
- rlimits on CPU time and address space, plus a wall-clock timeout,
- an audit hook that blocks sockets to anything but the fake API, file opens outside the
  run's temp directory, new imports, subprocesses, os.system, exec and fork. Its settings live in
  a closure, so the script cannot reach them through module globals.

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
        elif isinstance(node, ast.Attribute) and (node.attr in FORBIDDEN_ATTRS or node.attr.startswith(FORBIDDEN_ATTR_PREFIXES)):
            raise ScriptRejected(f"attribute {node.attr} is not allowed")
        elif isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in FORBIDDEN_NAMES):
            raise ScriptRejected(f"name {node.id} is not allowed")
        elif isinstance(node, ast.MatchClass):
            for name in node.kwd_attrs:
                if name.startswith("_") or name in FORBIDDEN_ATTRS or name.startswith(FORBIDDEN_ATTR_PREFIXES):
                    raise ScriptRejected(f"attribute {name} is not allowed in a match pattern")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name.startswith("_"):
            raise ScriptRejected(f"name {node.name} is not allowed")
        elif isinstance(node, ast.arg) and node.arg.startswith("_"):
            raise ScriptRejected(f"name {node.arg} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ScriptRejected("global and nonlocal are not allowed")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            raise ScriptRejected("async code is not allowed")


# Attribute names that reach frames, code objects or a module's insides without a leading underscore,
# plus str.format, whose field syntax can walk dunder attributes inside a plain string.
FORBIDDEN_ATTR_PREFIXES = ("gi_", "cr_", "ag_", "f_", "tb_", "co_")
FORBIDDEN_ATTRS = frozenset({"format", "format_map", "mro", "modules", "with_traceback"})

# The child's bootstrap. It runs with `python -I` and receives its config as argv[1] (JSON).
# The audit hook keeps its settings in a closure, not in module globals, and the script sees
# allowed modules only through proxies that hold their public, non-module attributes.
BOOTSTRAP = r"""
import json, os, resource, sys
cfg = json.loads(sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU, (cfg["cpu"], cfg["cpu"]))
mem = cfg["mem_mb"] * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
os.chdir(cfg["tmp"])
sys.path.insert(0, cfg["pkg_path"])
import builtins, io, contextlib, traceback, types
import math, datetime, collections, itertools, re, statistics, functools, _strptime, encodings.idna
from toolcut.taskdesk.client import TaskDesk, TaskDeskError
from toolcut.taskdesk.ops import OPS


def make_hook(tmp, api, allowed, block, realpath, fspath, sep):
    def hook(event, args):
        if event == "socket.connect":
            addr = args[1]
            if not (isinstance(addr, tuple) and tuple(addr[:2]) == api):
                raise PermissionError(f"network blocked: only the TaskDesk API at {api[0]}:{api[1]} is reachable")
        elif event in ("socket.sendto", "socket.sendmsg", "socket.bind"):
            raise PermissionError("network blocked: " + event)
        elif event == "socket.getaddrinfo":
            if args[0] not in (api[0], api[0].encode()):
                raise PermissionError(f"network blocked: lookup of {args[0]!r}")
        elif event == "open":
            path = args[0]
            if isinstance(path, int):
                return
            p = realpath(fspath(path))
            if isinstance(p, bytes):
                p = p.decode(errors="replace")
            if not (p == tmp or p.startswith(tmp + sep)):
                raise PermissionError(f"file access blocked outside the run's temp directory: {path!r}")
        elif event == "import":
            if args[0].split(".")[0] not in allowed:
                raise ImportError(f"import of {args[0]} is not allowed")
        elif event.startswith(block):
            raise PermissionError(f"blocked: {event}")
    return hook


hook = make_hook(os.path.realpath(cfg["tmp"]), (cfg["host"], cfg["port"]), frozenset(cfg["allowed"]),
                 ("subprocess.", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
                  "pty.", "ctypes.", "os.kill", "os.putenv", "os.unsetenv", "shutil.", "os.remove", "os.rmdir",
                  "os.rename", "os.unlink", "os.mkdir", "os.chmod", "os.chown", "os.link", "os.symlink", "webbrowser.",
                  "sys._getframe", "sys.settrace", "sys.setprofile", "object.__setattr__", "object.__delattr__"),
                 os.path.realpath, os.fspath, os.sep)


def proxy(mod):
    names = {k: v for k, v in vars(mod).items() if not k.startswith("_") and not isinstance(v, types.ModuleType)}
    return types.SimpleNamespace(**names)


MODULES = {name: proxy(sys.modules[name]) for name in cfg["allowed"] if name in sys.modules and name != "encodings"}


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name not in MODULES:
        raise ImportError(f"import of {name} is not allowed")
    return MODULES[name]


client = TaskDesk(f"http://{cfg['host']}:{cfg['port']}")
td = types.SimpleNamespace(**{op.name: (lambda n: lambda **kw: client.call(n, kw))(op.name) for op in OPS})
safe_builtins = {k: v for k, v in vars(builtins).items() if k not in cfg["forbidden"] and k not in ("open", "__loader__", "__spec__")}
safe_builtins["__import__"] = safe_import
safe_builtins["open"] = open
if cfg["hook_only"]:  # tests only: the audit hook with no other guard in front of it
    env = {"taskdesk": client, "TaskDeskError": TaskDeskError, "__name__": "__run_code__"}
else:
    env = {"taskdesk": td, "TaskDeskError": TaskDeskError, "__name__": "__run_code__", "__builtins__": safe_builtins}
code = sys.stdin.read()
compiled = compile(code, "<run_code>", "exec")
out = io.StringIO()
real_stdout = sys.stdout
sys.addaudithook(hook)
del hook, cfg
error = None
try:
    with contextlib.redirect_stdout(out):
        exec(compiled, env)
except BaseException as e:
    tb = traceback.extract_tb(e.__traceback__)
    line = next((f.lineno for f in reversed(tb) if f.filename == "<run_code>"), None)
    error = f"{type(e).__name__}: {e}" + (f" (script line {line})" if line else "")
real_stdout.write(json.dumps({"stdout": out.getvalue(), "error": error}))
"""


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


def _kill_group(child: subprocess.Popen) -> None:
    """Kill the child and anything it started, since it runs in its own session."""
    import os
    import signal

    try:
        os.killpg(child.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        child.kill()
    child.communicate()


def run_code(code: str, api_url: str, *, timeout: float = DEFAULT_TIMEOUT, memory_mb: int = DEFAULT_MEMORY_MB,
             skip_ast_check: bool = False) -> RunResult:
    """Run a script against the TaskDesk API in a limited child process.

    skip_ast_check exists only so tests can prove that the audit hook holds on its own. It also turns
    off the restricted builtins and the module proxies, so the script runs with only the hook.
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
               "host": url.hostname, "port": url.port, "allowed": list(ALLOWED_IMPORTS) + ["encodings"],
               "forbidden": sorted(FORBIDDEN_NAMES), "hook_only": skip_ast_check}
        child = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-I", "-c", BOOTSTRAP, json.dumps(cfg)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=tmp,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, start_new_session=True,
        )
        try:
            stdout, stderr = child.communicate(code, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(child)
            return RunResult("", f"TimeoutError: the script ran longer than {timeout:g} seconds and was stopped", timed_out=True)
        proc = subprocess.CompletedProcess(child.args, child.returncode, stdout, stderr)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
        if proc.returncode in (-9, -24):  # SIGKILL or SIGXCPU from the CPU limit
            return RunResult("", "TimeoutError: the script hit the CPU time limit and was stopped", timed_out=True)
        return RunResult("", f"SandboxError: {tail[0]}")
    return RunResult(payload.get("stdout", ""), payload.get("error"))
