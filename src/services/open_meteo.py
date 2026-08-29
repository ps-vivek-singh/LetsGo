from mcp_tools.weather_tools import WeatherTool


class OpenMeteoService:
    def __init__(self) -> None:
        self.tool = WeatherTool()

    def get_weather(self, location: str) -> dict:
        return self.tool.get_weather(location)
