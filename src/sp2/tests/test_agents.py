"""Tests for the Environment (the state authority that replaced the deprecated
EnvironmentAgent). Coordinator tests live in test_coordinator.py."""

import pytest

from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.environment.environment import Environment


def _env_with(signals, base, positions):
    env = Environment(Grid(5, 5))
    env.initialize(signals, base, positions)
    return env


def test_initialize_seeds_heuristics_and_positions():
    sig1 = Signal(1, Cell(0, 0), 0)
    sig2 = Signal(2, Cell(4, 4), 0)
    env = _env_with([sig1, sig2], Cell(2, 2), {0: Cell(2, 2)})

    # Heuristic table seeded with Manhattan per (cell, target).
    assert env.heuristic(Cell(0, 0), sig1.location) == 0.0
    assert env.heuristic(Cell(4, 4), sig1.location) == 8.0
    assert env.heuristic(Cell(2, 2), sig1.location) == 4.0
    # Authoritative position registry.
    assert env.position_of(0) == Cell(2, 2)
    assert env.occupant(Cell(2, 2)) == 0


def test_move_updates_world_and_rejects_dual_occupancy():
    env = _env_with([], Cell(2, 2), {0: Cell(2, 2), 1: Cell(2, 2)})

    env.move(0, Cell(2, 2), Cell(2, 3))
    assert env.position_of(0) == Cell(2, 3)
    assert env.cell_type(Cell(2, 3)) == CellType.AGENT
    # Vacated base cell stays BASE (it may still hold agent 1).
    assert env.cell_type(Cell(2, 2)) == CellType.BASE

    # Single-occupancy tripwire on a non-base cell.
    with pytest.raises(AssertionError):
        env.move(1, Cell(2, 2), Cell(2, 3))


def test_move_into_base_allows_multiple_occupants():
    env = _env_with([], Cell(2, 2), {0: Cell(2, 1), 1: Cell(2, 2)})
    # Agent 0 returns to base while agent 1 is already there -- allowed.
    env.move(0, Cell(2, 1), Cell(2, 2))
    assert env.position_of(0) == Cell(2, 2)
    assert env.position_of(1) == Cell(2, 2)


def test_update_heuristic_rejects_decrease():
    env = _env_with([Signal(1, Cell(0, 0), 0)], Cell(2, 2), {0: Cell(2, 2)})
    target = Cell(0, 0)
    env.update_heuristic(Cell(2, 2), target, 10.0)
    assert env.heuristic(Cell(2, 2), target) == 10.0
    with pytest.raises(AssertionError):
        env.update_heuristic(Cell(2, 2), target, 4.0)


def test_resolve_signal_lifecycle():
    sig = Signal(1, Cell(0, 0), 0)
    env = _env_with([sig], Cell(2, 2), {0: Cell(2, 2)})
    resolved = env.resolve_signal(Cell(0, 0), agent_id=0, tick=5)

    assert resolved is sig
    assert resolved.resolved_at_tick == 5
    assert resolved.resolved_by == 0
    assert 1 not in env.active_signals
    assert sig in env.resolved_signals
    assert env.cell_type(Cell(0, 0)) == CellType.FREE
    # Never re-activates.
    assert env.resolve_signal(Cell(0, 0), agent_id=0, tick=6) is None


def test_inject_signal_seeds_heuristics():
    env = _env_with([], Cell(2, 2), {0: Cell(2, 2)})
    sig = Signal(9, Cell(0, 4), 3)
    env.inject_signal(sig)
    assert 9 in env.active_signals
    assert env.cell_type(Cell(0, 4)) == CellType.SIGNAL
    assert env.heuristic(Cell(0, 0), Cell(0, 4)) == 4.0


def test_reservation_table():
    env = _env_with([], Cell(2, 2), {0: Cell(2, 2)})
    env.reserve(0, Cell(2, 3), tick=1)
    assert Cell(2, 3) in env.reservations(1)
    env.clear_reservations(1)
    assert env.reservations(1) == set()
