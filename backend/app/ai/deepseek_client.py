"""
DeepSeek Gateway Python 客户端
封装对 deepseek-app-server HTTP 服务的调用
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestException


class DeepSeekGatewayClient:
    """
    DeepSeek Gateway 客户端
    调用本地运行的 deepseek-app-server (Rust)
    """

    def __init__(self, base_url: str = "http://localhost:8787"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=10.0),
            headers={"Content-Type": "application/json"},
        )

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        response = await self.client.get(f"{self.base_url}/healthz")
        response.raise_for_status()
        return response.json()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        对话接口（通过 prompt 端点）

        Args:
            messages: [{"role": "user", "content": "..."}]
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token
            stream: 是否流式

        Returns:
            {"output": "...", "model": "...", "events": [...]}
        """
        # 将 messages 转换为 prompt 字符串
        prompt_text = "\n\n".join([
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        ])

        request = {
            "prompt": prompt_text,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self.client.post(
            f"{self.base_url}/prompt",
            json=request,
        )
        response.raise_for_status()
        return response.json()

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话（SSE）
        注意：deepseek-app-server 的 /prompt 端点可能不支持流式
        这里模拟实现，实际可能需要扩展 Rust 服务端点
        """
        # 当前 app-server 的 /prompt 是非流式的
        # 未来可扩展为 SSE 端点
        result = await self.chat(messages, model, temperature, max_tokens)
        yield result.get("output", "")

    async def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行工具

        Args:
            tool_name: 工具名（如 web_search, fetch_url 等）
            tool_args: 工具参数
            cwd: 工作目录

        Returns:
            工具执行结果
        """
        request = {
            "call": {
                "name": tool_name,
                "arguments": tool_args,
            },
        }
        if cwd:
            request["cwd"] = cwd

        response = await self.client.post(
            f"{self.base_url}/tool",
            json=request,
        )
        response.raise_for_status()
        return response.json()

    async def web_search(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[Dict[str, str]]:
        """
        联网搜索（通过工具执行）
        """
        result = await self.execute_tool(
            tool_name="web_search",
            tool_args={"query": query, "max_results": max_results},
        )

        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "results" in result:
            return result["results"]
        else:
            return []

    async def fetch_url(
        self,
        url: str,
        format: str = "text",
    ) -> str:
        """
        获取网页内容
        """
        result = await self.execute_tool(
            tool_name="fetch_url",
            tool_args={"url": url, "format": format},
        )

        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return result.get("content", "") or result.get("text", "")
        return ""

    async def get_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        response = await self.client.post(
            f"{self.base_url}/app",
            json={"method": "app/models", "params": {}},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("models", [])

    async def get_config(self, key: str) -> Any:
        """获取配置项"""
        response = await self.client.post(
            f"{self.base_url}/app",
            json={"method": "app/config/get", "params": {"key": key}},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("value")

    async def close(self) -> None:
        await self.client.aclose()


# 全局实例
deepseek_gateway = DeepSeekGatewayClient()
