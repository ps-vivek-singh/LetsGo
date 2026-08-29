from typing import Dict, List


class AgentRegistry:
    def __init__(self) -> None:
        self.agents: Dict[str, object] = {}

    def register(self, name: str, agent: object) -> None:
        self.agents[name] = agent

    def list_agents(self) -> List[str]:
        return list(self.agents.keys())

    def get_agent(self, name: str) -> object:
        return self.agents[name]
