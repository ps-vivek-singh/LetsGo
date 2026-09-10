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
            "User-Agent": "Antigravity-LetsGo/1.0",
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

    def route_intent(self, query: str, tools_manifest: Dict[str, List[str]]) -> Dict[str, Any]:
        """Use LLM to analyze query and decide which sections/tools to route to."""
        if not self.is_available():
            raise ValueError("LLM API key is not configured.")

        system_prompt = (
            "You are an intelligent intent router. Analyze the user's query and the available MCP tools manifest.\n"
            "Respond ONLY with a valid JSON object with the following schema:\n"
            "{\n"
            '  "sections": ["weather", "news", "commute", "breakfast", "itinerary", "email"],\n'
            '  "thought": "Brief explanation of routing rationale",\n'
            '  "location": "Origin city/location if specified",\n'
            '  "destination": "Destination city/place if commuting or traveling"\n'
            "}\n"
            f"Available tool servers and tools: {json.dumps(tools_manifest)}"
        )

        resp_text = self.complete(f"{system_prompt}\n\nUser Query: {query}", temperature=0.0)
        # Extract JSON from potential code block markers
        clean_text = resp_text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
            clean_text = clean_text.strip()

        try:
            return json.loads(clean_text)
        except Exception:
            logger.warning("Failed to parse LLM route_intent response: %s", resp_text)
            return {"sections": [], "thought": "Failed to parse JSON response"}

    def select_next_action(
        self,
        query: str,
        tools_manifest: Dict[str, List[str]],
        trace_history: List[Dict[str, Any]],
        tools_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ask LLM to view discovered tools, evaluate history, and pick the next tool or stop.

        Returns a dict::

            {
                "thought": "Reasoning for next action",
                "action": "server.tool_name" or "finish",
                "action_args": { ... }
            }
        """
        if not self.is_available():
            raise ValueError("LLM API key is not configured.")

        system_prompt = (
            "You are an agentic router and tool execution controller.\n"
            "Your job is to inspect the user query, available discovered MCP tools, and current execution history,\n"
            "then decide the NEXT tool to call or decide to FINISH if all requested information has been gathered.\n\n"
            "Discovered Tool Servers & Tools:\n"
            f"{json.dumps(tools_manifest, indent=2)}\n\n"
        )
        if tools_metadata:
            system_prompt += f"Tool Details/Parameters:\n{json.dumps(tools_metadata, indent=2)}\n\n"

        system_prompt += (
            "You MUST respond ONLY with a valid JSON object matching this exact format:\n"
            "{\n"
            '  "thought": "Your step-by-step reasoning about what info is missing or why you are done",\n'
            '  "action": "server_name.tool_name" or "finish",\n'
            '  "action_args": { "param1": "val1" }\n'
            "}\n\n"
            "Rules:\n"
            "1. 'action' must be either a valid 'server_name.tool_name' combination from Discovered Tool Servers (e.g. 'weather.get_weather', 'commute.get_commute_route', 'news.get_headlines', 'recipe.get_recipe', 'itinerary.get_itinerary', 'gmail.send_email_briefing') or 'finish'.\n"
            "2. If all user requests in the query have been fulfilled by previous observations, set 'action' to 'finish'.\n"
            "3. Provide exact arguments in 'action_args' needed by the tool.\n"
        )

        history_str = ""
        if trace_history:
            history_str = "Execution History So Far:\n"
            for step in trace_history:
                history_str += f"- Step {step.get('step')}: Thought: {step.get('thought')}\n"
                history_str += f"  Action: {step.get('action')}({json.dumps(step.get('action_args', {}))})\n"
                history_str += f"  Observation: {step.get('observation')}\n"
        else:
            history_str = "Execution History So Far: (None - this is Step 1)\n"

        prompt = f"{system_prompt}\nUser Query: {query}\n\n{history_str}\nDecide Next Action (JSON ONLY):"

        resp_text = self.complete(prompt, temperature=0.0)
        clean_text = resp_text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
            clean_text = clean_text.strip()

        try:
            parsed = json.loads(clean_text)
            action = parsed.get("action", "finish")
            thought = parsed.get("thought", "")
            action_args = parsed.get("action_args", {})
            return {
                "thought": thought,
                "action": action,
                "action_args": action_args if isinstance(action_args, dict) else {},
            }
        except Exception:
            logger.warning("Failed to parse LLM select_next_action response: %s", resp_text)
            return {
                "thought": "Failed to parse response, finishing execution.",
                "action": "finish",
                "action_args": {},
            }


# Backwards compatibility alias
XAIClient = LLMClient



