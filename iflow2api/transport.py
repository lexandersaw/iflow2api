"""上游传输层：支持 httpx 与 curl_cffi（TLS 指纹伪装）。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal, Optional

import httpx

logger = logging.getLogger("iflow2api")


TransportBackend = Literal["httpx", "curl_cffi"]


class UpstreamResponse:
    """统一响应包装，屏蔽不同 HTTP 客户端差异。"""

    def __init__(self, raw: Any):
        self.raw = raw

    @property
    def status_code(self) -> int:
        return int(getattr(self.raw, "status_code", 0))

    @property
    def headers(self) -> dict[str, str]:
        headers = getattr(self.raw, "headers", {})
        try:
            return dict(headers)
        except Exception:
            return {}

    @property
    def text(self) -> str:
        value = getattr(self.raw, "text", "")
        return value() if callable(value) else str(value)

    @property
    def content(self) -> bytes:
        value = getattr(self.raw, "content", b"")
        return value() if callable(value) else bytes(value)

    def json(self) -> Any:
        return self.raw.json()

    def raise_for_status(self) -> None:
        self.raw.raise_for_status()

    async def aread(self) -> bytes:
        if hasattr(self.raw, "aread"):
            return await self.raw.aread()
        return self.content

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        """统一流式字节迭代。"""
        if hasattr(self.raw, "aiter_bytes"):
            async for chunk in self.raw.aiter_bytes():
                yield chunk
            return

        if hasattr(self.raw, "aiter_content"):
            async for chunk in self.raw.aiter_content():
                yield chunk
            return

        if hasattr(self.raw, "iter_bytes"):
            for chunk in self.raw.iter_bytes():
                yield chunk
            return

        if hasattr(self.raw, "iter_content"):
            for chunk in self.raw.iter_content():
                yield chunk
            return

        content = await self.aread()
        if content:
            yield content


class BaseUpstreamTransport:
    """统一传输层接口。"""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> UpstreamResponse:
        raise NotImplementedError

    async def get(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> UpstreamResponse:
        return await self.request(
            "GET",
            url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    async def post(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> UpstreamResponse:
        return await self.request(
            "POST",
            url,
            headers=headers,
            data=data,
            json_body=json_body,
            timeout=timeout,
        )

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[UpstreamResponse]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class HttpxTransport(BaseUpstreamTransport):
    """httpx 传输实现。"""

    def __init__(
        self,
        *,
        timeout: float,
        follow_redirects: bool,
        proxy: Optional[str],
        trust_env: bool,
    ):
        kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(timeout, connect=min(10.0, timeout)),
            "follow_redirects": follow_redirects,
            "trust_env": trust_env,
        }
        if proxy:
            kwargs["proxy"] = proxy
        self._client = httpx.AsyncClient(**kwargs)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> UpstreamResponse:
        response = await self._client.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            json=json_body,
            timeout=timeout,
        )
        return UpstreamResponse(response)

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[UpstreamResponse]:
        async with self._client.stream(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            json=json_body,
            timeout=timeout,
        ) as response:
            yield UpstreamResponse(response)

    async def close(self) -> None:
        await self._client.aclose()


class CurlCffiTransport(BaseUpstreamTransport):
    """curl_cffi 传输实现（支持 impersonate）。"""

    def __init__(
        self,
        *,
        timeout: float,
        follow_redirects: bool,
        proxy: Optional[str],
        impersonate: str,
    ):
        from curl_cffi import requests as curl_requests

        self._session = curl_requests.AsyncSession(
            timeout=timeout,
            allow_redirects=follow_redirects,
        )
        self._proxy = proxy
        self._impersonate = impersonate

    def _build_kwargs(
        self,
        *,
        headers: Optional[dict[str, str]],
        params: Optional[dict[str, Any]],
        data: Any,
        json_body: Any,
        timeout: Optional[float],
        stream: bool = False,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "headers": headers,
            "params": params,
            "data": data,
            "json": json_body,
            "timeout": timeout,
            "impersonate": self._impersonate,
        }
        if stream:
            kwargs["stream"] = True
        if self._proxy:
            kwargs["proxy"] = self._proxy
        return kwargs

    async def _request_with_proxy_fallback(
        self,
        method: str,
        url: str,
        kwargs: dict[str, Any],
    ) -> Any:
        """兼容 curl_cffi 不同版本的 proxy/proxies 参数。"""
        try:
            return await self._session.request(method, url, **kwargs)
        except TypeError:
            if "proxy" in kwargs and kwargs["proxy"]:
                proxy = kwargs.pop("proxy")
                kwargs["proxies"] = {"http": proxy, "https": proxy}
                return await self._session.request(method, url, **kwargs)
            raise

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> UpstreamResponse:
        kwargs = self._build_kwargs(
            headers=headers,
            params=params,
            data=data,
            json_body=json_body,
            timeout=timeout,
            stream=False,
        )
        response = await self._request_with_proxy_fallback(method, url, kwargs)
        return UpstreamResponse(response)

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json_body: Any = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[UpstreamResponse]:
        kwargs = self._build_kwargs(
            headers=headers,
            params=params,
            data=data,
            json_body=json_body,
            timeout=timeout,
            stream=True,
        )

        # 新版接口：AsyncSession.stream(...) 是 async context manager
        if hasattr(self._session, "stream"):
            try:
                async with self._session.stream(method, url, **kwargs) as response:
                    yield UpstreamResponse(response)
                    return
            except TypeError:
                if kwargs.get("proxy"):
                    proxy = kwargs.pop("proxy")
                    kwargs["proxies"] = {"http": proxy, "https": proxy}
                    async with self._session.stream(method, url, **kwargs) as response:
                        yield UpstreamResponse(response)
                        return

        # 兼容旧接口：request(stream=True)
        response = await self._request_with_proxy_fallback(method, url, kwargs)
        try:
            yield UpstreamResponse(response)
        finally:
            if hasattr(response, "aclose"):
                await response.aclose()

    async def close(self) -> None:
        await self._session.close()


def create_upstream_transport(
    *,
    backend: TransportBackend,
    timeout: float,
    follow_redirects: bool,
    proxy: Optional[str],
    trust_env: bool = False,
    impersonate: str = "chrome124",
) -> BaseUpstreamTransport:
    """创建上游传输层实例。"""
    if backend == "curl_cffi":
        try:
            return CurlCffiTransport(
                timeout=timeout,
                follow_redirects=follow_redirects,
                proxy=proxy,
                impersonate=impersonate,
            )
        except Exception as e:
            logger.warning("curl_cffi 不可用，回退 httpx: %s", e)

    return HttpxTransport(
        timeout=timeout,
        follow_redirects=follow_redirects,
        proxy=proxy,
        trust_env=trust_env,
    )
