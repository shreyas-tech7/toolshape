"""Broken-case check for the sandbox tests.

Turns off the audit hook and the memory limit, then runs the limit tests. They must fail.
This shows the tests catch a sandbox without its guards. Run: .venv/bin/python scripts/prove_sandbox_tests.py
"""

import subprocess
import sys

CODE = r'''
import sys
import pytest
import toolcut.sandbox as s
s.BOOTSTRAP = s.BOOTSTRAP.replace("sys.addaudithook(_hook)", "pass").replace(
    "resource.setrlimit(resource.RLIMIT_AS, (mem, mem))", "pass")
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", "tests/test_sandbox.py", "-k",
                      "raw_socket or files_outside or memory or subprocess"]))
'''

r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, timeout=600)  # noqa: S603 - fixed argv, our own code
print(r.stdout[-1500:])
if r.returncode == 0:
    sys.exit("FAIL: the sandbox tests passed with the guards turned off")
print("OK: the sandbox tests fail when the guards are off")
