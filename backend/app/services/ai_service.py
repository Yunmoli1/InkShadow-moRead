"""AI summarization: local Ollama by default; optional OpenAI-compatible API.

All AI settings are stored locally. If the model is unreachable, a friendly
error is raised (the app must not crash).
"""
from __future__ import annotations

import httpx

from .netenv import should_proxy


class AiError(Exception):
    """User-facing AI error (message is safe to show)."""


async def summarize(text: str, settings: dict) -> str:
    base_url = (settings.get("ai_base_url") or "http://localhost:11434").rstrip("/")
    api_key = settings.get("ai_api_key") or ""
    model = settings.get("ai_model") or "llama3"
    style = settings.get("ai_style") or "ollama"  # ollama | openai
    proxy = (settings.get("proxy_url") or "").strip()
    client_kwargs = {"proxy": proxy} if should_proxy(base_url, proxy) else {}
    prompt = (
        "你是一位中文阅读助手。请用简洁的中文为以下小说章节内容生成一段摘要"
        "（150字以内），概括主要情节与人物，不要编造内容。\n\n章节内容：\n"
        + text[:12000]
    )
    try:
        if style == "openai":
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=120, headers=headers, **client_kwargs) as client:
                resp = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        # default: Ollama native API
        async with httpx.AsyncClient(timeout=120, **client_kwargs) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message", {}).get("content") or "").strip()
    except httpx.ConnectError:
        raise AiError(
            f"无法连接 AI 服务（{base_url}）。请确认本地 Ollama 已启动，"
            "或前往「设置」配置外部 API。"
        )
    except httpx.HTTPStatusError as exc:
        raise AiError(f"AI 服务返回错误（HTTP {exc.response.status_code}），请检查模型名称与配置。")
    except (KeyError, IndexError, ValueError):
        raise AiError("AI 服务响应格式异常，请检查配置。")


_SUMMARY_PROMPT = (
    "你是一位中文阅读助手。请用简洁的中文为以下小说章节内容生成一段摘要"
    "（150字以内），概括主要情节与人物，不要编造内容。\n\n章节内容：\n{body}"
)


async def stream_summarize(text: str, settings: dict):
    """流式生成摘要，逐段 yield 增量文本。错误以 AiError 抛出。"""
    import json as _json

    base_url = (settings.get("ai_base_url") or "http://localhost:11434").rstrip("/")
    api_key = settings.get("ai_api_key") or ""
    model = settings.get("ai_model") or "llama3"
    style = settings.get("ai_style") or "ollama"
    proxy = (settings.get("proxy_url") or "").strip()
    client_kwargs = {"proxy": proxy} if should_proxy(base_url, proxy) else {}
    prompt = _SUMMARY_PROMPT.format(body=text[:12000])
    try:
        if style == "openai":
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=180, headers=headers, **client_kwargs) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = _json.loads(data)
                        except ValueError:
                            continue
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
            return
        # default: Ollama native streaming (NDJSON)
        async with httpx.AsyncClient(timeout=180, **client_kwargs) as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        obj = _json.loads(line)
                    except ValueError:
                        continue
                    delta = (obj.get("message") or {}).get("content", "")
                    if delta:
                        yield delta
                    if obj.get("done"):
                        break
    except httpx.ConnectError:
        raise AiError(
            f"无法连接 AI 服务（{base_url}）。请确认本地 Ollama 已启动，"
            "或前往「设置」配置外部 API。"
        )
    except httpx.HTTPStatusError as exc:
        raise AiError(f"AI 服务返回错误（HTTP {exc.response.status_code}），请检查模型名称与配置。")
    except (KeyError, IndexError, ValueError):
        raise AiError("AI 服务响应格式异常，请检查配置。")
