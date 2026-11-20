"""Each shape runs as a real MCP server over stdio with the official SDK."""

import json

import pytest

from toolcut.sessions import InProcessSession, McpSession


@pytest.mark.parametrize("shape_key", ["A", "B", "C"])
def test_mcp_tool_list_matches_in_process(api, shape_key):
    with McpSession(shape_key, api.url) as m:
        mcp_tools = m.list_tools()
    local = InProcessSession(shape_key, api.url).list_tools()
    assert json.dumps(mcp_tools, sort_keys=True) == json.dumps(local, sort_keys=True)


def test_mcp_calls_and_errors(api):
    with McpSession("A", api.url) as m:
        ok = m.call("get_task", {"task_id": 2})
        bad = m.call("get_task", {"task_id": 999})
    assert not ok.is_error and json.loads(ok.text)["id"] == 2
    assert bad.is_error and "not found" in bad.text
    with McpSession("C", api.url) as m:
        r = m.call("run_code", {"code": "print(taskdesk.get_user(user_id=3)['name'])"})
    assert r.text.strip() == "Aiko Tanaka"


def test_mcp_server_refuses_a_non_local_api():
    from toolcut.mcp_server import main

    with pytest.raises(SystemExit):
        main(["--shape", "A", "--api-url", "http://10.0.0.1:80"])
