from abc import ABC, abstractmethod
from collections import deque

from src.sp2.messages.messages import Message


class Agent(ABC):
    message_callback = None

    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox: deque[Message] = deque()

    def send_message(self, receiver: "Agent", message: Message) -> None:
        """Post a message directly to another agent's inbox."""
        receiver.inbox.append(message)
        if Agent.message_callback is not None:
            Agent.message_callback(message)

    def drain_inbox(self) -> list[Message]:
        """Remove and return all messages from inbox."""
        messages = list(self.inbox)
        self.inbox.clear()
        return messages

    @abstractmethod
    def step(self, tick: int) -> None:
        """Execute one simulation tick."""
