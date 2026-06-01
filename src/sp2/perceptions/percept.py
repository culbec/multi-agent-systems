from abc import ABC, abstractmethod


class Percept(ABC):
    """Something an agent can perceive in a single tick.

    Mirrors the AIMA ``Percept``: it is built by the Environment's
    ``get_percept`` (the ``see: S -> P`` function) from the world ``State`` and
    the perceiving agent's vantage. Because an agent receives only one percept
    per turn, a ``Percept`` may incorporate the results of several sensors.
    """

    @abstractmethod
    def __str__(self) -> str:
        ...