import anthropic
from config.settings import ANTHROPIC_API_KEY
from agent.prompts import build_system_prompt
from agent.tools import build_full_context
from agent.memory import ConversationMemory

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# One memory instance per session
# In production this would be per-user, stored in DB
memory = ConversationMemory(max_turns=10)


def ask(question: str, current_balance: float) -> str:
    """
    Main entry point. Takes a user question and current balance,
    returns a plain English answer grounded in real financial data.

    Args:
        question: The user's plain English question
        current_balance: Live balance from Plaid get_balances()

    Returns:
        Claude's response as a string
    """
    # Build context from real data
    context = build_full_context(current_balance)

    # Build system prompt with injected context
    system_prompt = build_system_prompt(context)

    # Add user question to memory
    memory.add_user_message(question)

    # Call Claude
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system_prompt,
        messages=memory.get_history(),
    )

    answer = response.content[0].text

    # Store assistant response in memory for multi-turn context
    memory.add_assistant_message(answer)

    return answer


def reset_conversation():
    """Clear conversation history — call between sessions."""
    memory.clear()


if __name__ == "__main__":
    from integrations.plaid_client import (
        create_sandbox_public_token,
        exchange_public_token,
        get_balances,
    )
    import time

    # Get real sandbox balance
    print("Connecting to Plaid sandbox...")
    public_token = create_sandbox_public_token()
    access_token = exchange_public_token(public_token)
    time.sleep(3)
    accounts = get_balances(access_token)

    liquid_types = {"checking", "savings"}
    current_balance = sum(
        acc["balance"] for acc in accounts
        if str(acc["subtype"]).lower() in liquid_types
        and acc["balance"] is not None
    )
    print(f"Current liquid balance: ${current_balance:,.2f}")

    # Test conversation
    questions = [
        "What is my current cash position?",
        "Will I have enough cash to cover my bills this month?",
        "What are my biggest expenses right now?",
    ]

    for q in questions:
        print(f"\nQ: {q}")
        answer = ask(q, current_balance)
        print(f"A: {answer}")
        print("-" * 60)
