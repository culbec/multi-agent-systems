from src.sp2.agents.agent import Agent
from src.sp2.algorithms.lrta_star import lrta_star_step
from src.sp2.domain.cell import Cell
from src.sp2.domain.reservation import Reservation
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    FreeMessage,
    HUpdateMessage,
    MoveMessage,
    NeighborQueryMessage,
    NeighborResponseMessage,
    ReserveMessage,
    TerminateMessage,
)


class RescueAgent(Agent):
    def __init__(
        self, agent_id: int, start_position: Cell, environment: Agent, coordinator: Agent, peers: list[Agent]
    ):
        super().__init__(agent_id)
        self.position = start_position
        self.target: Cell | None = None
        self.current_h: float | None = None
        self.received_reservations: set[Reservation] = set()
        self.movement_history: list[Cell] = [start_position]
        self.halted = False
        self.free_sent = False
        self.wait_count = 0
        self.environment = environment
        self.coordinator = coordinator
        self.peers = peers

    def step(self, tick: int) -> None:
        """Execute Sub-phase A of simulation tick."""
        messages = self.drain_inbox()

        for msg in messages:
            if isinstance(msg, AssignMessage):
                self.target = msg.target
                self.free_sent = False
                self.current_h = None
            elif isinstance(msg, ReserveMessage):
                self.received_reservations.add(
                    Reservation(agent_id=msg.sender_id, cell=msg.cell, tick=msg.reserve_tick)
                )
            elif isinstance(msg, ClearedMessage):
                if self.target is not None and msg.signal == self.target:
                    self.target = None
                    self.current_h = None
                    # Send FreeMessage to Coordinator
                    free_msg = FreeMessage(
                        sender_id=self.agent_id,
                        receiver_id=self.coordinator.agent_id,
                        tick=tick,
                        agent_id=self.agent_id,
                        position=self.position,
                    )
                    self.send_message(self.coordinator, free_msg)
                    self.free_sent = True
            elif isinstance(msg, TerminateMessage):
                self.halted = True

        if self.halted:
            return

        # Check if we are already at the target
        if self.target is not None and self.position == self.target:
            # Broadcast ClearedMessage to peers, environment, and coordinator
            cleared_msg = ClearedMessage(sender_id=self.agent_id, receiver_id=-1, tick=tick, signal=self.position)
            for peer in self.peers:
                self.send_message(peer, cleared_msg)
            self.send_message(self.environment, cleared_msg)
            self.send_message(self.coordinator, cleared_msg)

            # Send FreeMessage to Coordinator
            free_msg = FreeMessage(
                sender_id=self.agent_id,
                receiver_id=self.coordinator.agent_id,
                tick=tick,
                agent_id=self.agent_id,
                position=self.position,
            )
            self.send_message(self.coordinator, free_msg)

            self.target = None
            self.current_h = None
            self.free_sent = True
            return

        if self.target is None:
            if not self.free_sent:
                free_msg = FreeMessage(
                    sender_id=self.agent_id,
                    receiver_id=self.coordinator.agent_id,
                    tick=tick,
                    agent_id=self.agent_id,
                    position=self.position,
                )
                self.send_message(self.coordinator, free_msg)
                self.free_sent = True

        destination = self.target if self.target is not None else self.environment.base
        if destination is None or self.position == destination:
            # Already at destination (e.g. idle at base)
            return

        # Send NeighborQueryMessage to Environment, including our current destination!
        query_msg = NeighborQueryMessage(
            sender_id=self.agent_id,
            receiver_id=self.environment.agent_id,
            tick=tick,
            position=self.position,
            target=destination,
        )
        self.send_message(self.environment, query_msg)

    def step_act(self, tick: int) -> None:
        """Execute Sub-phase B of simulation tick."""
        if self.halted:
            return

        destination = self.target if self.target is not None else self.environment.base
        if destination is None or self.position == destination:
            return

        # Drain inbox to collect NeighborResponse AND any concurrent ReserveMessages
        messages = self.drain_inbox()
        response = None
        for msg in messages:
            if isinstance(msg, NeighborResponseMessage):
                response = msg
            elif isinstance(msg, ReserveMessage):
                self.received_reservations.add(
                    Reservation(agent_id=msg.sender_id, cell=msg.cell, tick=msg.reserve_tick)
                )
            else:
                # Put back other messages
                self.inbox.append(msg)

        if response is None:
            # No neighbor response, wait
            self.wait_count += 1
            return

        # Identify positions of idle peers standing still at base (they act as permanent obstacles)
        idle_peer_positions = {
            peer.position
            for peer in self.peers
            if peer.target is None and peer.position == self.environment.base and not getattr(peer, "halted", False)
        }

        # Extract neighbor data, filtering out cells occupied by IDLE agents standing still at base
        neighbors = []
        for cell, _, h_val in response.neighbors:
            if cell not in idle_peer_positions:
                neighbors.append((cell, h_val))

        # Initialize current_h if None
        if self.current_h is None:
            # Try to find current cell's h in neighbors or default to Manhattan distance to destination
            self.current_h = float(self.position.manhattan_distance(destination))

        # Build reserved cells for current tick
        reserved_cells = {res.cell for res in self.received_reservations if res.tick == tick}

        # Add all active/moving peer positions to reserved_cells to prevent colliding with them
        for peer in self.peers:
            peer_dest = peer.target if peer.target is not None else self.environment.base
            if peer_dest is not None and peer.position != peer_dest and not getattr(peer, "halted", False):
                reserved_cells.add(peer.position)

        # Call LRTA* step
        updated_h, best_move = lrta_star_step(self.current_h, neighbors, reserved_cells)

        # Send HUpdateMessage to Environment, including our destination!
        h_update = HUpdateMessage(
            sender_id=self.agent_id,
            receiver_id=self.environment.agent_id,
            tick=tick,
            cell=self.position,
            value=updated_h,
            target=destination,
        )
        self.send_message(self.environment, h_update)

        # Also update our local current_h to updated_h
        self.current_h = updated_h

        if best_move is None:
            self.wait_count += 1
            self.received_reservations.clear()
            return

        # Collision resolution
        conflicting_agents = [
            res.agent_id for res in self.received_reservations if res.cell == best_move and res.tick == tick
        ]
        if conflicting_agents and any(self.agent_id < other_id for other_id in conflicting_agents):
            # We yield (wait)
            self.wait_count += 1
            self.received_reservations.clear()
            return

        # Proceed with move
        # Broadcast ReserveMessage
        reserve_msg = ReserveMessage(
            sender_id=self.agent_id, receiver_id=-1, tick=tick, cell=best_move, reserve_tick=tick
        )
        for peer in self.peers:
            self.send_message(peer, reserve_msg)

        # Send MoveMessage to Environment
        move_msg = MoveMessage(
            sender_id=self.agent_id,
            receiver_id=self.environment.agent_id,
            tick=tick,
            from_cell=self.position,
            to_cell=best_move,
        )
        self.send_message(self.environment, move_msg)

        # Update position and h-value
        best_move_h = 0.0
        for cell, h_val in neighbors:
            if cell == best_move:
                best_move_h = h_val
                break

        self.position = best_move
        self.current_h = best_move_h
        self.movement_history.append(best_move)

        # Clear received reservations
        self.received_reservations.clear()
