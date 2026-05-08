"""
LLM Gateway 服务
基于 DeepSeek-TUI 架构设计的 Python 实现
支持多 Provider（DeepSeek/OpenAI/Ollama）、自动重试、流式传输、健康监控
"""

import asyncio
import json
import random
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestException


class ProviderType(StrEnum):
    """支持的 LLM Provider"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    FIREWORKS = "fireworks"


class ConnectionHealth(StrEnum):
    """连接健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class RateLimitConfig:
    """限流配置"""
    requests_per_second: float = 8.0
    burst_size: int = 16


@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # system / user / assistant / tool
    content: str = ""
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    reasoning_content: str | None = None
    name: str | None = None


@dataclass
class LLMRequest:
    """LLM 请求"""
    messages: list[LLMMessage]
    model: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4096
    stream: bool = False
    tools: list[dict] | None = None
    response_format: dict | None = None
    reasoning_effort: str | None = None  # off / low / medium / high


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    reasoning_content: str | None = None
    tool_calls: list[dict] | None = None
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    finish_reason: str = ""


@dataclass
class StreamEvent:
    """流式事件"""
    event_type: str  # content / reasoning / tool_call / done / error
    data: str = ""
    tool_call_chunk: dict | None = None


class TokenBucket:
    """令牌桶限流器"""

    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    async def wait(self) -> None:
        while not await self.acquire():
            await asyncio.sleep(0.1)


class LLMProvider:
    """LLM Provider 基类"""

    def __init__(
        self,
        provider_type: ProviderType,
        api_key: str,
        base_url: str,
        default_model: str,
        retry_config: RetryConfig | None = None,
    ):
        self.provider_type = provider_type
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.retry_config = retry_config or RetryConfig()
        self.health = ConnectionHealth.HEALTHY
        self.consecutive_failures = 0
        self.last_failure_time: float | None = None
        self.rate_limiter = TokenBucket(
            rate=RateLimitConfig().requests_per_second,
            burst=RateLimitConfig().burst_size,
        )
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_request_payload(self, request: LLMRequest) -> dict[str, Any]:
        """构建请求体"""
        messages = []
        for msg in request.messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.reasoning_content and msg.role == "assistant":
                m["reasoning_content"] = msg.reasoning_content
            if msg.tool_calls and msg.role == "assistant":
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id and msg.role == "tool":
                m["tool_call_id"] = msg.tool_call_id
                m["name"] = msg.name or "tool"
            messages.append(m)

        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }

        if request.tools:
            payload["tools"] = request.tools

        if request.response_format:
            payload["response_format"] = request.response_format

        # DeepSeek reasoning
        if (
            self.provider_type == ProviderType.DEEPSEEK
            and request.reasoning_effort
            and request.reasoning_effort in ("high", "max")
        ):
            payload["model"] = "deepseek-reasoner"

        return payload

    async def _do_request(self, payload: dict[str, Any]) -> httpx.Response:
        """执行原始 HTTP 请求"""
        await self.rate_limiter.wait()
        return await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        )

    async def _with_retry(self, fn: Callable, *args, **kwargs) -> Any:
        """带重试的请求包装器"""
        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                result = await fn(*args, **kwargs)
                # 成功，重置失败计数
                self.consecutive_failures = 0
                if self.health == ConnectionHealth.DEGRADED:
                    self.health = ConnectionHealth.HEALTHY
                return result

            except httpx.HTTPStatusError as e:
                last_exception = e
                status = e.response.status_code

                # 429 限流，读取 Retry-After
                if status == 429:
                    retry_after = e.response.headers.get("retry-after")
                    wait_time = float(retry_after) if retry_after else self._calculate_delay(attempt)
                    await asyncio.sleep(wait_time)
                    continue

                # 5xx 错误可重试
                if status >= 500:
                    await asyncio.sleep(self._calculate_delay(attempt))
                    continue

                # 4xx 客户端错误不重试
                raise BadRequestException(f"LLM API 错误 {status}: {e.response.text}") from e

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                self.consecutive_failures += 1
                self.last_failure_time = time.monotonic()

                if self.consecutive_failures >= 2:
                    self.health = ConnectionHealth.DEGRADED

                await asyncio.sleep(self._calculate_delay(attempt))
                continue

            except Exception as e:
                raise BadRequestException(f"LLM 请求异常: {str(e)}") from e

        # 全部重试失败
        self.health = ConnectionHealth.UNHEALTHY
        raise BadRequestException(
            f"LLM 请求在 {self.retry_config.max_retries} 次重试后仍然失败: {str(last_exception)}"
        )

    def _calculate_delay(self, attempt: int) -> float:
        """计算退避延迟"""
        delay = self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt)
        delay = min(delay, self.retry_config.max_delay)
        if self.retry_config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return delay

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """非流式对话"""
        payload = self._build_request_payload(request)
        response = await self._with_retry(self._do_request, payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice.get("message", {})

        return LLMResponse(
            content=message.get("content", ""),
            reasoning_content=message.get("reasoning_content"),
            tool_calls=message.get("tool_calls"),
            model=data.get("model", self.default_model),
            provider=self.provider_type.value,
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", ""),
        )

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[StreamEvent, None]:
        """流式对话（SSE）"""
        request.stream = True
        payload = self._build_request_payload(request)

        try:
            await self.rate_limiter.wait()
            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=httpx.Timeout(300.0, connect=30.0),
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        yield StreamEvent(event_type="done")
                        return

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})

                        # 推理内容
                        if "reasoning_content" in delta and delta["reasoning_content"]:
                            yield StreamEvent(
                                event_type="reasoning",
                                data=delta["reasoning_content"],
                            )

                        # 普通内容
                        if "content" in delta and delta["content"]:
                            yield StreamEvent(
                                event_type="content",
                                data=delta["content"],
                            )

                        # 工具调用
                        if "tool_calls" in delta and delta["tool_calls"]:
                            yield StreamEvent(
                                event_type="tool_call",
                                tool_call_chunk=delta["tool_calls"][0],
                            )

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            yield StreamEvent(event_type="error", data=str(e))

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 尝试调用 models 列表接口
            resp = await self.client.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
                timeout=10.0,
            )
            if resp.status_code == 200:
                self.health = ConnectionHealth.HEALTHY
                self.consecutive_failures = 0
                return True
        except Exception:
            pass

        # 简单请求测试
        try:
            test_req = LLMRequest(
                messages=[LLMMessage(role="user", content="hi")],
                max_tokens=5,
            )
            await self.chat(test_req)
            self.health = ConnectionHealth.HEALTHY
            self.consecutive_failures = 0
            return True
        except Exception:
            pass

        return False


class LLMGateway:
    """
    LLM 网关 - 多 Provider 管理、自动降级、统一接口
    基于 DeepSeek-TUI 的 LlmClient + Retry + Health 设计
    """

    def __init__(self):
        self.providers: dict[str, LLMProvider] = {}
        self.provider_order: list[str] = []
        self._init_providers()

    def _init_providers(self) -> None:
        """初始化 Provider"""
        # DeepSeek
        if settings.DEEPSEEK_API_KEY:
            self._add_provider(
                ProviderType.DEEPSEEK,
                settings.DEEPSEEK_API_KEY,
                settings.DEEPSEEK_BASE_URL,
                "deepseek-chat",
            )

        # OpenAI
        if settings.OPENAI_API_KEY:
            self._add_provider(
                ProviderType.OPENAI,
                settings.OPENAI_API_KEY,
                "https://api.openai.com/v1",
                "gpt-4o",
            )

        # Ollama (本地)
        if settings.OLLAMA_BASE_URL:
            self._add_provider(
                ProviderType.OLLAMA,
                "ollama",
                settings.OLLAMA_BASE_URL,
                "qwen2.5:14b",
            )

    def _add_provider(
        self,
        provider_type: ProviderType,
        api_key: str,
        base_url: str,
        default_model: str,
    ) -> None:
        name = provider_type.value
        self.providers[name] = LLMProvider(
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
        )
        if name not in self.provider_order:
            self.provider_order.append(name)

    def set_preferred_provider(self, provider_name: str) -> None:
        """设置首选 Provider"""
        if provider_name in self.provider_order:
            self.provider_order.remove(provider_name)
            self.provider_order.insert(0, provider_name)

    async def chat(
        self,
        request: LLMRequest,
        preferred_provider: str | None = None,
    ) -> LLMResponse:
        """
        统一对话接口，自动 Provider 选择和降级
        """
        order = self._get_provider_order(preferred_provider)
        last_error = None

        for name in order:
            provider = self.providers.get(name)
            if not provider:
                continue

            # 跳过不健康且最近失败的 Provider
            if (
                provider.health == ConnectionHealth.UNHEALTHY
                and provider.last_failure_time
                and time.monotonic() - provider.last_failure_time < 15
            ):
                continue

            try:
                print(f"🤖 使用 Provider: {name} ({provider.default_model})")
                response = await provider.chat(request)
                response.provider = name
                return response

            except Exception as e:
                last_error = e
                print(f"⚠️ Provider {name} 失败: {e}")
                continue

        raise BadRequestException(
            f"所有 Provider 均不可用。已尝试: {order}。最后错误: {last_error}"
        )

    async def chat_stream(
        self,
        request: LLMRequest,
        preferred_provider: str | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """统一流式对话接口"""
        order = self._get_provider_order(preferred_provider)
        last_error = None

        for name in order:
            provider = self.providers.get(name)
            if not provider:
                continue

            try:
                async for event in provider.chat_stream(request):
                    yield event
                return

            except Exception as e:
                last_error = e
                continue

        yield StreamEvent(event_type="error", data=f"所有 Provider 均不可用: {last_error}")

    async def chat_with_tools(
        self,
        request: LLMRequest,
        tool_executor: Callable,
        max_tool_rounds: int = 5,
        preferred_provider: str | None = None,
    ) -> LLMResponse:
        """
        支持工具调用的对话（ReAct 循环）

        Args:
            request: 初始请求
            tool_executor: 工具执行函数 (tool_name, tool_args) -> result_str
            max_tool_rounds: 最大工具调用轮数
        """
        messages = list(request.messages)

        for _round_num in range(max_tool_rounds):
            req = LLMRequest(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=request.tools,
            )

            response = await self.chat(req, preferred_provider)

            # 没有工具调用，直接返回
            if not response.tool_calls:
                return response

            # 执行工具
            for tool_call in response.tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                tool_id = tool_call["id"]

                print(f"🔧 执行工具: {tool_name}({tool_args})")
                try:
                    tool_result = await tool_executor(tool_name, tool_args)
                except Exception as e:
                    tool_result = f"工具执行错误: {str(e)}"

                # 添加 assistant 的 tool_call 消息
                messages.append(LLMMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=[tool_call],
                ))

                # 添加 tool 结果消息
                messages.append(LLMMessage(
                    role="tool",
                    content=str(tool_result),
                    tool_call_id=tool_id,
                    name=tool_name,
                ))

        # 达到最大轮数，返回最后一次结果
        return response

    def _get_provider_order(self, preferred: str | None = None) -> list[str]:
        """确定 Provider 尝试顺序"""
        order = []
        if preferred and preferred in self.provider_order:
            order.append(preferred)
        for name in self.provider_order:
            if name not in order:
                order.append(name)
        return order if order else list(self.providers.keys())

    async def health_check_all(self) -> dict[str, bool]:
        """检查所有 Provider 健康状态"""
        results = {}
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        return results

    async def close(self) -> None:
        """关闭所有连接"""
        for provider in self.providers.values():
            await provider.close()


# 全局网关实例
llm_gateway = LLMGateway()
