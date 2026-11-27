from app.prompt_management import load_prompt

AGENT_ROLES = ("plan", "legal", "fiscal", "planning", "synthesis")


def agent_prompt(role):
    return load_prompt(f"assistant/agent-{role}")
