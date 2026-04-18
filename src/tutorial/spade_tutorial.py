import os
from typing import Any

import spade
from spade_llm import ChatAgent, LLMAgent, LLMProvider, load_env_vars


def create_llm_provider(
    model: str,
    base_url: str | None = None,
    **kwargs: dict[str, Any],
) -> LLMProvider:
    return LLMProvider(
        model=model,
        base_url=base_url,
        **kwargs,
    )


def create_llm_agent(
    jid: str,
    password: str,
    provider: LLMProvider,
    system_prompt: str | None = None,
) -> LLMAgent:
    return LLMAgent(
        jid=jid,
        password=password,
        provider=provider,
        system_prompt=system_prompt,
    )


async def main() -> None:
    load_env_vars("../.env")

    spade_server = os.environ.get("SPADE_SERVER", "localhost")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    # Will use locally deployed Ollama
    provider = create_llm_provider("ollama/llama3.2", base_url=ollama_url)
    llm_agent = create_llm_agent(
        jid=f"assistant@{spade_server}",
        password="assistant123",  # noqa: S106
        provider=provider,
        system_prompt="You are a specialized assistant in poetry.",
    )

    chat_agent = ChatAgent(
        jid=f"user@{spade_server}",
        password="user123",  # noqa: S106
        target_agent_jid=f"assistant@{spade_server}",
    )

    try:
        await llm_agent.start()
        await chat_agent.start()

        print("You can now chat with your assistant. Type 'exit' to quit.")
        await chat_agent.run_interactive()
    except KeyboardInterrupt:
        print("Bye, bye!")
    finally:
        await chat_agent.stop()
        await llm_agent.stop()
        print("Agents stopped successfully!")


if __name__ == "__main__":
    spade.run(main())
