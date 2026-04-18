import pathlib

from spade_llm import load_env_vars

load_env_vars(pathlib.Path(__file__).parent.resolve() / ".env")
