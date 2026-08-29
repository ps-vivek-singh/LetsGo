"""LLM API Client for multi-provider tool calling and natural language synthesis.

Provides an OpenAI-compatible interface supporting NVIDIA NIM, Groq, OpenRouter,
Google Gemini, and OpenAI with JSON Schema function/tool calling schemas.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from services.config import Config

logger = logging.getLogger("commute_commander.llm")


class LLMClient:
    """Multi-provider OpenAI-compatible LLM client (NVIDIA NIM, Groq, OpenRouter, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._explicit_key = api_key
        self._explicit_model = model
        self._explicit_base_url = base_url

    @property
    def api_key(self) -> str:
        if self._explicit_key is not None:
            return self._explicit_key
        return Config.get_llm_key()

    @property
    def base_url(self) -> str:
        if self._explicit_base_url:
            return self._explicit_base_url
        key = self.api_key
        if key.startswith("nvapi-"):
            return "https://integrate.api.nvidia.com/v1/chat/completions"
        if key.startswith("gsk_"):
            return "https://api.groq.com/openai/v1/chat/completions"
        if key.startswith("sk-or-"):
            return "https://openrouter.ai/api/v1/chat/completions"
        if key.startswith("AIzaSy"):
            return "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        if key.startswith("sk-"):
            return "https://api.openai.com/v1/chat/completions"
        return "https://integrate.api.nvidia.com/v1/chat/completions"

    @property
    def model(self) -> str:
        if self._explicit_model:
            return self._explicit_model
        env_model = Config.get_llm_model()
        if env_model:
            if "/" not in env_model:
                if "nemotron" in env_model:
                    return f"nvidia/{env_model}"
                if "llama" in env_model:
                    return f"meta/{env_model}"
            return env_model

        key = self.api_key
        if key.startswith("nvapi-"):
            return "meta/llama-3.2-11b-vision-instruct"
        if key.startswith("gsk_"):
            return "llama-3.3-70b-versatile"
        if key.startswith("sk-or-"):
            return "meta-llama/llama-3.3-70b-instruct:free"
        if key.startswith("AIzaSy"):
            return "gemini-1.5-flash"
        if key.startswith("sk-"):
            return "gpt-4o-mini"
        return "meta/llama-3.2-11b-vision-instruct"

    def is_available(self) -> bool:
        """Check if an LLM API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def format_mcp_tools(self, tools_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert FastMCP / ToolRegistry tool schemas to OpenAI-compatible tool format.

        Args:
            tools_dict: Dictionary mapping tool names to tool metadata/parameters.
        """
        formatted_tools = []
        for name, tool_info in tools_dict.items():
            desc = tool_info.get("description", f"Tool {name}")
            parameters = tool_info.get("parameters", tool_info.get("schema", {}))

            if not isinstance(parameters, dict) or "properties" not in parameters:
                parameters = {
                    "type": "object",
                    "properties": parameters if isinstance(parameters, dict) else {},
                    "required": tool_info.get("required", []),
                }

            formatted_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": parameters,
                },
            })
        return formatted_tools

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str | Dict[str, Any] = "auto",
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Send chat completion request to configured LLM endpoint.

        Returns raw JSON response dictionary containing choices, message, tool_calls, etc.
        """
        if not self.is_available():
            raise ValueError("LLM API key is not configured.")

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        sanitized_api_key = self.api_key.strip().strip('"').strip("'")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {sanitized_api_key}",
            "User-Agent": "Antigravity-CommuteCommander/1.0",
        }

        try:
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                duration_ms = (time.perf_counter() - t0) * 1000
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                comp_tokens = usage.get("completion_tokens", 0)
                try:
                    from services.telemetry import telemetry
                    provider = "nim" if "nvidia" in self.base_url else ("groq" if "groq" in self.base_url else "openai")
                    telemetry.llm(provider, self.model, duration_ms, prompt_tokens, comp_tokens, status="OK")
                except Exception:
                    pass
                return data
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            logger.error("LLM API HTTPError %d: %s", err.code, err_body)
            try:
                from services.telemetry import telemetry
                telemetry.error("LLM", f"HTTPError {err.code}: {err_body}")
            except Exception:
                pass
            raise RuntimeError(f"LLM API error {err.code}: {err_body}") from err
        except Exception as exc:
            logger.error("LLM API request failed: %s", exc)
            try:
                from services.telemetry import telemetry
                telemetry.error("LLM", f"Request failed: {exc}")
            except Exception:
                pass
            raise RuntimeError(f"Failed to communicate with LLM API: {exc}") from exc

    def complete(self, prompt: str, temperature: float = 0.2) -> str:
        """Send a single prompt string and return the assistant's text content response."""
        res = self.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        choices = res.get("choices", [])
        if choices and "message" in choices[0]:
            return choices[0]["message"].get("content", "")
        return ""


# Backwards compatibility alias
XAIClient = LLMClient


