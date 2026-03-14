import contextlib
from typing import cast

import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

NUM_AGENTS: int = 5


class HelloAgent(Agent):
    class HelloBehaviour(OneShotBehaviour):
        async def run(self) -> None:
            agent = cast(Agent, self.agent) if self.agent is not None else None
            print(f"Hello, I am {agent.name}!")  # ty:ignore[unresolved-attribute]

    async def setup(self) -> None:
        self.add_behaviour(self.HelloBehaviour())


async def main() -> None:
    global NUM_AGENTS

    for i in range(NUM_AGENTS):
        jid = f"agent_{i + 1}@localhost"
        agent = HelloAgent(jid, "password", verify_security=False)
        try:
            await agent.start()
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    ## pyjabber complains a lot regarding TLS handshakes on local environment
    ## redirecting it to NULL and relying on the internal logger
    with contextlib.redirect_stderr(None):
        spade.run(main(), embedded_xmpp_server=True)
