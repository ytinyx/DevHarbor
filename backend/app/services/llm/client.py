import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.services.context_compression import prompt_cache_model_kwargs
from app.services.model_providers import ModelProviderError, ResolvedModelConfig, resolve_model_config


class LLMClient:
    def __init__(self, config: ResolvedModelConfig | None = None) -> None:
        config = config or resolve_model_config()
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.model = config.model
        self.enabled = config.enabled
        self.source = config.source

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _cache_options(self) -> dict[str, Any]:
        # Custom compatible endpoints need not implement OpenAI's cache options.
        return prompt_cache_model_kwargs() if self.source == "environment" else {}

    def _provider_failure(self, error: Exception) -> None:
        if self.source != "provider":
            return
        status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
        message = "模型服务暂时无法完成请求，请检查设置中的接口地址、模型名称及网络连接。"
        if status in (401, 403):
            message = "模型服务拒绝访问，请在设置中检查 API 密钥和模型权限。"
        elif status == 429:
            message = "模型服务限流或额度不足，请稍后重试并检查供应商额度。"
        raise ModelProviderError(status_code=502, message=message) from None

    async def chat_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {}

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
        }
        payload.update(self._cache_options())
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                self._provider_failure(exc)
                return {}

    async def chat_text(self, system_prompt: str, user_message: str) -> str:
        if not self.enabled:
            return ""

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        payload.update(self._cache_options())
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                return str(response.json()["choices"][0]["message"].get("content") or "")
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                self._provider_failure(exc)
                return ""

    async def chat_text_stream(self, system_prompt: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if not self.enabled:
            return

        payload_messages = [{"role": "system", "content": system_prompt}, *messages]
        payload: dict[str, Any] = {"model": self.model, "messages": payload_messages, "stream": True}
        payload.update(self._cache_options())
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line.removeprefix("data: ").strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield str(content)
            except httpx.HTTPStatusError as exc:
                self._provider_failure(exc)
                return
            except httpx.HTTPError as exc:
                self._provider_failure(exc)
                raise
