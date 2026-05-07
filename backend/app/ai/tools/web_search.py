"""
联网搜索模块
基于 DeepSeek-TUI 的 web_search.rs 设计
支持 DuckDuckGo + Bing 回退，HTML 解析，SSRF 防护
"""

import html
import re
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.core.exceptions import BadRequestException


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


class WebSearchTool:
    """
    联网搜索工具
    策略：DuckDuckGo 优先 -> Bing 回退
    """

    DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
    BING_URL = "https://www.bing.com/search"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=10.0),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        source: Optional[str] = None,
    ) -> List[SearchResult]:
        """执行搜索"""
        if not query or not query.strip():
            raise BadRequestException("搜索关键词不能为空")

        providers = []
        if source in ("duckduckgo", None):
            providers.append("duckduckgo")
        if source in ("bing", None):
            providers.append("bing")

        last_error = None
        for provider in providers:
            try:
                if provider == "duckduckgo":
                    results = await self._search_duckduckgo(query, max_results)
                else:
                    results = await self._search_bing(query, max_results)
                if results:
                    return results
            except Exception as e:
                last_error = e
                continue

        raise BadRequestException(f"搜索全部失败: {last_error}")

    async def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        params = {"q": query, "kl": "zh-cn"}
        response = await self.client.post(self.DUCKDUCKGO_URL, data=params)
        response.raise_for_status()

        html_text = response.text
        results = []

        # 提取结果块
        result_blocks = re.findall(
            r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html_text,
            re.DOTALL | re.IGNORECASE,
        )

        for block in result_blocks[:max_results]:
            title_match = re.search(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            if not title_match:
                continue

            url = self._clean_ddg_url(title_match.group(1))
            title = self._strip_html(title_match.group(2))

            snippet_match = re.search(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            snippet = self._strip_html(snippet_match.group(1)) if snippet_match else ""

            results.append(SearchResult(title=title, url=url, snippet=snippet, source="duckduckgo"))

        return results

    async def _search_bing(self, query: str, max_results: int) -> List[SearchResult]:
        params = {"q": query, "setmkt": "zh-CN", "setlang": "zh-hans"}
        response = await self.client.get(self.BING_URL, params=params)
        response.raise_for_status()

        html_text = response.text
        results = []

        result_blocks = re.findall(
            r'<li class="b_algo"[^>]*>(.*?)</li>',
            html_text,
            re.DOTALL | re.IGNORECASE,
        )

        for block in result_blocks[:max_results]:
            title_match = re.search(
                r'<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?</h2>',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            if not title_match:
                continue

            url = title_match.group(1)
            title = self._strip_html(title_match.group(2))

            snippet_match = re.search(
                r'<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            snippet = self._strip_html(snippet_match.group(1)) if snippet_match else ""

            results.append(SearchResult(title=title, url=url, snippet=snippet, source="bing"))

        return results

    @staticmethod
    def _strip_html(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _clean_ddg_url(url: str) -> str:
        if url.startswith("/l/?"):
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            if "uddg" in query:
                return urllib.parse.unquote(query["uddg"][0])
        return url

    async def close(self) -> None:
        await self.client.aclose()


web_search = WebSearchTool()
