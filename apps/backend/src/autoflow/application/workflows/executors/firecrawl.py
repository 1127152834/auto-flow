"""WebRPA Firecrawl browser executors adapted to the CloakBrowser session.

Source: reference/WebRPA/backend/app/executors/ai_firecrawl.py@5ccb900e8dcf1530aae66f676d87593c416c7ebb
License: LICENSE.WebRPA
Changes: the private Chromium launcher and direct sitemap HTTP client are replaced
by temporary pages in the run's existing CloakBrowser session. Screenshot output
implements the already-approved Studio field.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urljoin, urlparse

import html2text  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from autoflow.domain.workflows.browser import BrowserPagePort
from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_bool, to_int


@asynccontextmanager
async def _temporary_page(
    context: ExecutionContext,
    url: str,
    *,
    timeout_ms: float = 30_000,
) -> AsyncIterator[BrowserPagePort]:
    if context.browser is None:
        raise RuntimeError("没有打开的页面")
    original_id = context.browser.current_page().id
    page = await context.browser.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout_ms=timeout_ms)
        yield page
    finally:
        await page.close()
        try:
            context.browser.select_page(original_id)
        except Exception:  # noqa: BLE001,S110 - the inspected page may be user-closed.
            pass


def _selectors(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _matching(soup: Any, selector: str) -> list[Any]:
    if selector.startswith((".", "#")) or any(mark in selector for mark in "[ >:+~"):
        return list(soup.select(selector))
    return list(soup.find_all(selector))


def _prepare_html(
    html: str,
    *,
    only_main_content: bool,
    include_tags: str = "",
    exclude_tags: str = "",
) -> Any:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    for selector in _selectors(exclude_tags):
        for element in _matching(soup, selector):
            element.decompose()
    if only_main_content:
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", {"id": re.compile(r"content|main", re.IGNORECASE)})
            or soup.find("div", {"class": re.compile(r"content|main", re.IGNORECASE)})
            or soup.body
        )
        if main:
            soup = BeautifulSoup(str(main), "html.parser")
    if include_tags:
        filtered = BeautifulSoup("", "html.parser")
        for selector in _selectors(include_tags):
            for element in _matching(soup, selector):
                filtered.append(element)
        soup = filtered
    return soup


def _page_result(url: str, soup: Any, formats: list[str]) -> dict[str, Any]:
    title = soup.title.string if soup.title else ""
    result: dict[str, Any] = {"url": url, "title": title}
    if "markdown" in formats:
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.body_width = 0
        result["markdown"] = converter.handle(str(soup))
    if "html" in formats:
        result["html"] = str(soup)
    if "text" in formats:
        result["text"] = soup.get_text(separator="\n", strip=True)
    return result


async def _page_links(page: BrowserPagePort) -> list[str]:
    value = await page.evaluate(
        "Array.from(document.querySelectorAll('a[href]'), element => element.href)"
    )
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _accepted_url(
    candidate: str,
    *,
    domain: str,
    include_subdomains: bool,
    search: str = "",
) -> bool:
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return False
    if include_subdomains:
        if not parsed.netloc.endswith(domain):
            return False
    elif parsed.netloc != domain:
        return False
    return not search or search.lower() in candidate.lower()


async def _sitemap_links(context: ExecutionContext, url: str) -> list[str]:
    parsed = urlparse(url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    async with _temporary_page(context, sitemap_url, timeout_ms=20_000) as page:
        html = await page.content()
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", html, re.IGNORECASE)


class FirecrawlScrapeExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "firecrawl_scrape"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = self.get_text(config.get("url", ""), context)
        variable_name = config.get("variableName", "scrape_result")
        if not url:
            return ModuleResult(success=False, error="URL 不能为空")
        try:
            formats = list(config.get("formats") or ["markdown"])
            await context.send_progress(f"🔥 正在抓取页面: {url}", "info")
            await context.send_progress(f"格式: {', '.join(formats)}", "info")
            async with _temporary_page(
                context,
                url,
                timeout_ms=max(1, to_int(config.get("timeout"), 30_000, context)),
            ) as page:
                wait_for = self.get_text(config.get("waitFor", ""), context)
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=5_000)
                    except Exception:  # noqa: BLE001,S110 - source treats this as best effort.
                        pass
                html = await page.content()
                soup = _prepare_html(
                    html,
                    only_main_content=to_bool(
                        config.get("onlyMainContent"), True, context
                    ),
                    include_tags=self.get_text(config.get("includeTags", ""), context),
                    exclude_tags=self.get_text(config.get("excludeTags", ""), context),
                )
                result = _page_result(url, soup, formats)
                result["metadata"] = {
                    "title": result["title"],
                    "description": "",
                    "language": soup.html.get("lang", "") if soup.html else "",
                }
                meta = soup.find("meta", {"name": "description"})
                if meta:
                    result["metadata"]["description"] = meta.get("content", "")
                if "screenshot" in formats:
                    if context.node_artifacts is None:
                        raise RuntimeError("截图产物存储未配置")
                    name = f"firecrawl-{context.current_execution_id or 'page'}.png"
                    result["screenshot"] = await context.node_artifacts.write_bytes(
                        name=name,
                        content=await page.screenshot(full_page=True),
                        mime_type="image/png",
                    )
            context.set_variable(str(variable_name), result)
            content = result.get("markdown", result.get("html"))
            preview = (
                content[:300] + "..."
                if isinstance(content, str) and len(content) > 300
                else content
            )
            if preview is None:
                preview = json.dumps(result, ensure_ascii=False, indent=2)[:300] + "..."
            return ModuleResult(
                success=True,
                message=(
                    f"✅ 成功抓取页面数据，已保存到变量 {variable_name}\n\n预览:\n{preview}"
                ),
                data=result,
            )
        except Exception as error:  # noqa: BLE001 - provider errors become node errors.
            return ModuleResult(success=False, error=f"抓取失败: {error}")


class FirecrawlMapExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "firecrawl_map"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = self.get_text(config.get("url", ""), context)
        variable_name = config.get("variableName", "map_result")
        if not url:
            return ModuleResult(success=False, error="URL 不能为空")
        try:
            search = self.get_text(config.get("search", ""), context)
            include_subdomains = to_bool(config.get("includeSubdomains"), False, context)
            limit = max(1, to_int(config.get("limit"), 5_000, context))
            domain = urlparse(url).netloc
            found: set[str] = set()
            await context.send_progress(f"🗺️ 正在抓取网站链接: {url}", "info")
            async with _temporary_page(context, url) as page:
                links = await _page_links(page)
            for link in links:
                absolute = urljoin(url, link)
                if _accepted_url(
                    absolute,
                    domain=domain,
                    include_subdomains=include_subdomains,
                    search=search,
                ):
                    found.add(absolute)
                if len(found) >= limit:
                    break
            if not to_bool(config.get("ignoreSitemap"), True, context) and len(found) < limit:
                try:
                    await context.send_progress(
                        f"🗺️ 正在读取站点地图: {urlparse(url).scheme}://{domain}/sitemap.xml",
                        "info",
                    )
                    for link in await _sitemap_links(context, url):
                        if _accepted_url(
                            link,
                            domain=domain,
                            include_subdomains=include_subdomains,
                            search=search,
                        ):
                            found.add(link)
                        if len(found) >= limit:
                            break
                except Exception as error:  # noqa: BLE001 - source ignores sitemap failure.
                    await context.send_progress(
                        f"⚠️ 站点地图读取失败(忽略): {error}", "warning"
                    )
            result = sorted(found)
            context.set_variable(str(variable_name), result)
            preview = "\n".join(result[:10])
            if len(result) > 10:
                preview += f"\n... 还有 {len(result) - 10} 个链接"
            return ModuleResult(
                success=True,
                message=(
                    f"✅ 成功抓取 {len(result)} 个链接，已保存到变量 {variable_name}"
                    f"\n\n链接预览:\n{preview}"
                ),
                data=result,
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"链接抓取失败: {error}")


class FirecrawlCrawlExecutor(ModuleExecutor):
    requires_browser = True

    @property
    def module_type(self) -> str:
        return "firecrawl_crawl"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        url = self.get_text(config.get("url", ""), context)
        variable_name = config.get("variableName", "crawl_result")
        if not url:
            return ModuleResult(success=False, error="URL 不能为空")
        try:
            max_depth = max(0, to_int(config.get("maxDepth"), 2, context))
            limit = max(1, to_int(config.get("limit"), 100, context))
            include = _selectors(self.get_text(config.get("includePaths", ""), context))
            exclude = _selectors(self.get_text(config.get("excludePaths", ""), context))
            formats = list(config.get("formats") or ["markdown"])
            only_main = to_bool(config.get("onlyMainContent"), True, context)
            allow_external = to_bool(config.get("allowExternalLinks"), False, context)
            allow_backward = to_bool(config.get("allowBackwardLinks"), False, context)
            parsed_start = urlparse(url)
            domain = parsed_start.netloc
            start_path = parsed_start.path or "/"
            prefix = start_path.rsplit("/", 1)[0] + "/"
            queue: list[tuple[str, int]] = [(url, 0)]
            if not to_bool(config.get("ignoreSitemap"), True, context):
                try:
                    for item in await _sitemap_links(context, url):
                        parsed = urlparse(item)
                        if parsed.scheme not in {"http", "https"}:
                            continue
                        if not allow_external and parsed.netloc != domain:
                            continue
                        if not allow_backward and not (parsed.path or "/").startswith(
                            prefix
                        ):
                            continue
                        queue.append((item, 1))
                except Exception as error:  # noqa: BLE001 - sitemap remains optional.
                    await context.send_progress(
                        f"⚠️ 站点地图读取失败(忽略): {error}", "warning"
                    )
            visited: set[str] = set()
            results: list[dict[str, Any]] = []
            await context.send_progress(f"🕷️ 正在爬取整个网站: {url}", "info")
            await context.send_progress(
                f"最大深度: {max_depth}, 页面限制: {limit}", "info"
            )
            while queue and len(results) < limit:
                if context.cancellation is not None:
                    context.cancellation.raise_if_cancelled()
                current, depth = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if depth > max_depth:
                    continue
                if include and not any(item in current for item in include):
                    continue
                if exclude and any(item in current for item in exclude):
                    continue
                await context.send_progress(
                    f"⏳ 正在爬取 ({len(results) + 1}/{limit}): {current}", "info"
                )
                try:
                    async with _temporary_page(context, current) as page:
                        soup = _prepare_html(
                            await page.content(), only_main_content=only_main
                        )
                        results.append(_page_result(current, soup, formats))
                        links = await _page_links(page) if depth < max_depth else []
                    for link in links:
                        absolute = urljoin(current, link)
                        parsed = urlparse(absolute)
                        if parsed.scheme not in {"http", "https"}:
                            continue
                        if not allow_external and parsed.netloc != domain:
                            continue
                        if not allow_backward and not (parsed.path or "/").startswith(prefix):
                            continue
                        if absolute not in visited:
                            queue.append((absolute, depth + 1))
                except Exception as error:  # noqa: BLE001 - source skips failed pages.
                    await context.send_progress(
                        f"⚠️ 跳过页面 {current}: {error}", "warning"
                    )
            context.set_variable(str(variable_name), results)
            summary = f"成功爬取 {len(results)} 个页面"
            if results and "markdown" in results[0]:
                summary += f"\n\n第一个页面预览:\n{results[0]['markdown'][:200]}..."
            return ModuleResult(
                success=True,
                message=f"✅ {summary}，已保存到变量 {variable_name}",
                data=results,
            )
        except Exception as error:  # noqa: BLE001
            return ModuleResult(success=False, error=f"全站爬取失败: {error}")


FIRECRAWL_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    FirecrawlScrapeExecutor,
    FirecrawlMapExecutor,
    FirecrawlCrawlExecutor,
)
