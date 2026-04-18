import pathlib

from spade_llm import load_env_vars

_env_file = pathlib.Path(__file__).parent.resolve() / ".env"
if _env_file.is_file():
    load_env_vars(_env_file)
