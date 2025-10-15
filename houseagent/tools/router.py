# ABOUTME: Tool router for executing tools with timeout and error handling
# ABOUTME: Manages tool registry, execution policy, and result formatting

from typing import Dict, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolRequest:
    """Request to execute a tool"""

    tool_name: str
    params: Dict[str, Any]


class ToolRouter:
    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self.timeout_seconds = 5
        self._executor = ThreadPoolExecutor(max_workers=1)

    def execute(self, request: ToolRequest) -> Dict[str, Any]:
        """Execute tool with timeout and error handling"""
        tool = self.tools.get(request.tool_name)
        if not tool:
            return {"error": "Unknown tool"}

        try:
            # Execute with timeout
            result = self._execute_with_timeout(
                tool.execute, request.params, self.timeout_seconds
            )
            return result
        except FuturesTimeoutError:
            return {"error": "Tool timeout"}
        except Exception as e:
            return {"error": str(e)}

    def _execute_with_timeout(self, func: Callable, args: Dict, timeout: int) -> Any:
        """Execute function with timeout using ThreadPoolExecutor"""
        future = self._executor.submit(func, args)
        try:
            result = future.result(timeout=timeout)
            return result
        except FuturesTimeoutError:
            # Cancel the future and raise
            future.cancel()
            raise

    def get_catalog(self) -> str:
        """Get catalog of available tools with descriptions"""
        catalog_parts = []
        for tool_name, tool in self.tools.items():
            if hasattr(tool, "get_description"):
                description = tool.get_description()
                catalog_parts.append(f"{tool_name}: {description}")
            else:
                catalog_parts.append(tool_name)
        return "\n\n".join(catalog_parts)

    def __del__(self):
        """Cleanup executor on deletion"""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
