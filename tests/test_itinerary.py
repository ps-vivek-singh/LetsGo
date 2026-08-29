"""Tests for ItineraryAgent and itinerary_tools."""
from agents.itinerary_agent import ItineraryAgent
from mcp_tools.itinerary_tools import get_itinerary
from nlp.query_parser import QueryParser


def test_get_itinerary_heuristic():
    result = get_itinerary(location="Rome", days=3, budget="moderate")
    assert result["location"] == "Rome"
    assert result["days_count"] == 3
    assert len(result["days"]) == 3
    assert "morning" in result["days"][0]


def test_itinerary_agent_structured():
    agent = ItineraryAgent()
    res = agent.run_structured(location="Kyoto", days=2, budget="luxury")
    assert res["section"] == "itinerary"
    assert res["status"] == "success"
    assert res["data"]["location"] == "Kyoto"


def test_query_parser_itinerary_intent():
    parser = QueryParser()
    parsed = parser.parse("Give me a 3-day travel itinerary and trip plan for Tokyo")
    assert "itinerary" in parsed["sections"]


def test_query_parser_trip_with_modifiers():
    parser = QueryParser()
    parsed = parser.parse("plan a trip to Bali Indonesia for 3 days in a moderate budget.")
    assert "itinerary" in parsed["sections"]
    assert "Bali" in parsed["location"]
    assert parsed["days"] == 3
    assert parsed["budget"] == "moderate"
    assert parsed["destination"] == ""


def test_itinerary_agent_error_handling():
    agent = ItineraryAgent()
    # Mocking failure
    import unittest.mock as mock
    with mock.patch("agents.itinerary_agent.get_itinerary", side_effect=ValueError("LLM quota exceeded")):
        res = agent.run_structured("Nowhere")
        assert res["section"] == "itinerary"
        assert res["status"] == "error"
        assert isinstance(res["error"], dict)
        assert res["error"]["code"] == "agent_error"
        assert "LLM quota exceeded" in res["error"]["message"]
