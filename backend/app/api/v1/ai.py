"""
AI 服务 API 路由
通过 DeepSeek Gateway (Rust) 提供 LLM 对话、联网搜索、工具执行
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ai.deepseek_client import deepseek_gateway
from app.core.dependencies import get_current_user, require_role
from app.core.exceptions import BadRequestException
from app.core.security import validate_url_for_ssrf
from app.models.user import UserRole

# Security fix V-003: all AI endpoints now require authentication
router = APIRouter(dependencies=[Depends(get_current_user)])

# Security fix V-003: allowed tool whitelist for /tool endpoint
ALLOWED_TOOLS = {"calculator", "search", "fetch_url"}


class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., description="对话消息列表")
    model: str | None = Field(None, description="模型名称")
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=8192)
    stream: bool = Field(False, description="是否流式输出")


class ChatResponse(BaseModel):
    output: str
    model: str = ""
    events: list[dict] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(10, ge=1, le=50)


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


class ToolExecuteRequest(BaseModel):
    tool_name: str
    tool_args: dict = {}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> Any:
    """LLM 对话"""
    try:
        result = await deepseek_gateway.chat(
            messages=request.messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
        )
        return ChatResponse(
            output=result.get("output", ""),
            model=result.get("model", ""),
            events=result.get("events", []),
        )
    except Exception as e:
        raise BadRequestException(f"LLM 对话失败: {str(e)}") from e


@router.post("/search", response_model=list[SearchResultItem])
async def web_search(request: SearchRequest) -> Any:
    """联网搜索"""
    try:
        results = await deepseek_gateway.web_search(
            query=request.query,
            max_results=request.max_results,
        )
        return [SearchResultItem(**r) for r in results]
    except Exception as e:
        raise BadRequestException(f"搜索失败: {str(e)}") from e


@router.post("/fetch-url")
async def fetch_url(url: str, format: str = "text") -> Any:
    """获取网页内容"""
    # Security fix V-007: SSRF protection
    validate_url_for_ssrf(url)
    try:
        content = await deepseek_gateway.fetch_url(url, format)
        return {"url": url, "content": content, "format": format}
    except Exception as e:
        raise BadRequestException(f"获取网页失败: {str(e)}") from e


@router.post("/tool")
async def execute_tool(
    request: ToolExecuteRequest,
    current_user=Depends(require_role(UserRole.admin)),  # Security fix V-003: admin only
) -> Any:
    """执行工具（管理员专用）"""
    # Security fix V-003: enforce tool whitelist
    if request.tool_name not in ALLOWED_TOOLS:
        raise BadRequestException(
            f"工具 '{request.tool_name}' 不在允许列表中"
        )
    try:
        result = await deepseek_gateway.execute_tool(
            tool_name=request.tool_name,
            tool_args=request.tool_args,
        )
        return result
    except Exception as e:
        raise BadRequestException(f"工具执行失败: {str(e)}") from e


@router.get("/models")
async def list_models() -> Any:
    """列出可用模型"""
    try:
        models = await deepseek_gateway.get_models()
        return {"models": models}
    except Exception as e:
        raise BadRequestException(f"获取模型列表失败: {str(e)}") from e


@router.get("/health")
async def health() -> Any:
    """DeepSeek Gateway 健康检查"""
    try:
        status = await deepseek_gateway.health_check()
        return {"gateway_status": status, "ok": True}
    except Exception as e:
        return {"gateway_status": "unavailable", "error": str(e), "ok": False}
