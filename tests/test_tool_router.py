# ABOUTME: Tests for tool router framework with timeout and error handling
# ABOUTME: Validates tool registration, execution, and policy enforcement

from houseagent.tools.router import ToolRouter, ToolRequest
from unittest.mock import Mock
import time


def test_tool_router_executes_tools():
    """Test ToolRouter can execute registered tools"""
    router = ToolRouter()

    # Register mock tool
    mock_tool = Mock()
    mock_tool.execute.return_value = {"result": "success"}
    router.tools["test_tool"] = mock_tool

    request = ToolRequest(tool_name="test_tool", params={"arg": "value"})
    result = router.execute(request)

    assert result["result"] == "success"
    mock_tool.execute.assert_called_once_with({"arg": "value"})


def test_tool_router_handles_unknown_tools():
    """Test ToolRouter returns error for unknown tools"""
    router = ToolRouter()

    request = ToolRequest(tool_name="nonexistent", params={})
    result = router.execute(request)

    assert "error" in result
    assert result["error"] == "Unknown tool"


def test_tool_router_handles_tool_exceptions():
    """Test ToolRouter catches and returns errors from tools"""
    router = ToolRouter()

    # Register tool that raises exception
    mock_tool = Mock()
    mock_tool.execute.side_effect = ValueError("Tool failed")
    router.tools["failing_tool"] = mock_tool

    request = ToolRequest(tool_name="failing_tool", params={})
    result = router.execute(request)

    assert "error" in result
    assert "Tool failed" in result["error"]


def test_tool_router_timeout_handling():
    """Test ToolRouter handles timeout for slow tools"""
    router = ToolRouter()
    router.timeout_seconds = 1  # Short timeout for testing

    # Register tool that takes too long
    mock_tool = Mock()

    def slow_execute(params):
        time.sleep(2)
        return {"result": "should not reach"}

    mock_tool.execute = slow_execute
    router.tools["slow_tool"] = mock_tool

    request = ToolRequest(tool_name="slow_tool", params={})
    result = router.execute(request)

    assert "error" in result
    assert "timeout" in result["error"].lower()


def test_tool_router_get_catalog():
    """Test ToolRouter returns catalog of available tools"""
    router = ToolRouter()

    mock_tool1 = Mock()
    mock_tool2 = Mock()
    router.tools["tool_one"] = mock_tool1
    router.tools["tool_two"] = mock_tool2

    catalog = router.get_catalog()

    assert "tool_one" in catalog
    assert "tool_two" in catalog
