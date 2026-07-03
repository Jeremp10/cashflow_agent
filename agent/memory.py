class ConversationMemory:
    """
    Manages conversation history for multi-turn chat.
    Keeps the last N turns to avoid exceeding context limits.
    """

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.history = []

    def add_user_message(self, content: str):
        self.history.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str):
        self.history.append({"role": "assistant", "content": content})
        self._trim()

    def get_history(self) -> list:
        return self.history.copy()

    def clear(self):
        self.history = []

    def _trim(self):
        """Keep only the last max_turns * 2 messages (user + assistant pairs)."""
        max_messages = self.max_turns * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]
