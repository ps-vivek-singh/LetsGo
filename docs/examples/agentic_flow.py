from agents.orchestrator import OrchestratorAgent
from services.session_manager import SessionManager


if __name__ == "__main__":
    session_manager = SessionManager(storage_dir="./sessions")
    orchestrator = OrchestratorAgent(session_manager=session_manager)
    session_id = session_manager.start_session("demo")

    query = "I woke up in the morning. Give me weather, news, and a quick breakfast idea with eggs."
    result = orchestrator.run(query, session_id=session_id)
    print(result)
