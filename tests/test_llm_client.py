"""Tests for LLMClient service."""
from unittest.mock import patch, MagicMock
from services.llm_client import LLMClient


def test_llm_client_availability():
    client = LLMClient(api_key="nvapi-test_key", model="meta/llama-3.1-8b-instruct")
    assert client.is_available() is True
    assert client.base_url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert client.model == "meta/llama-3.1-8b-instruct"

    client_empty = LLMClient(api_key="", model="meta/llama-3.1-8b-instruct")
    assert client_empty.is_available() is False


def test_llm_client_provider_urls():
    # NVIDIA
    c_nv = LLMClient(api_key="nvapi-12345")
    assert c_nv.base_url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert c_nv.model == "meta/llama-3.1-8b-instruct"

    # Groq
    c_groq = LLMClient(api_key="gsk_12345")
    assert c_groq.base_url == "https://api.groq.com/openai/v1/chat/completions"

    # OpenRouter
    c_or = LLMClient(api_key="sk-or-12345")
    assert c_or.base_url == "https://openrouter.ai/api/v1/chat/completions"

    # Gemini
    c_gem = LLMClient(api_key="AIzaSy12345")
    assert c_gem.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def test_format_mcp_tools():
    client = LLMClient(api_key="test_key")
    tools_dict = {
        "get_weather": {
            "description": "Fetch weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        }
    }
    formatted = client.format_mcp_tools(tools_dict)
    assert len(formatted) == 1
    assert formatted[0]["type"] == "function"
    assert formatted[0]["function"]["name"] == "get_weather"
    assert formatted[0]["function"]["description"] == "Fetch weather"
