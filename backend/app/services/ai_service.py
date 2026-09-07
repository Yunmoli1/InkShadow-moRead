"""AI summarization: local Ollama by default; optional OpenAI-compatible API.

All AI settings are stored locally. If the model is unreachable, a friendly
error is raised (the app must not crash).
"""
from __future__ import annotations

import httpx


class AiError(Exception):
    """User-facing AI error (message is safe to show)."""


async def summarize(text: str, settings: dict) -> str:
    base_url = (settings.get("ai_base_url") or "http://localhost:11434").rstrip("/")
    api_key = settings.get("ai_api_key") or ""
    model = settings.get("ai_model") or "llama3"
    style = settings.get("ai_style") or "ollama"  # ollama | openai
    prompt = (
        "你是一位中文阅读助手。请用简洁的中文为以下小说章节内容生成一段摘要"
        "（150字以内），概括主要情节与人物，不要编造内容。\n\n章节内容：\n"
        + text[:12000]
    )
    try:
        if style == "openai":
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=120, headers=headers) as client:
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
        async with httpx.AsyncClient(timeout=120) as client:
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
