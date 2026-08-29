from mcp_tools.news_tools import NewsTool


class NewsFeedService:
    def __init__(self) -> None:
        self.tool = NewsTool()

    def get_headlines(self) -> list:
        return self.tool.get_headlines()
