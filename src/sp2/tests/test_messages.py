from src.sp2.domain.cell import Cell, CellType
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    FreeMessage,
    HUpdateMessage,
    MoveMessage,
    NeighborQueryMessage,
    NeighborResponseMessage,
    NewSignalMessage,
    ReserveMessage,
    TerminateMessage,
)


def test_messages():
    sender = 1
    receiver = 2
    tick = 10

    # 1. AssignMessage
    target_cell = Cell(1, 2)
    msg = AssignMessage(sender_id=sender, receiver_id=receiver, tick=tick, target=target_cell)
    assert msg.sender_id == sender
    assert msg.receiver_id == receiver
    assert msg.tick == tick
    assert msg.target == target_cell
    assert msg.msg_type == "ASSIGN"

    # 2. FreeMessage
    msg_free = FreeMessage(sender_id=sender, receiver_id=receiver, tick=tick, agent_id=sender, position=target_cell)
    assert msg_free.agent_id == sender
    assert msg_free.position == target_cell
    assert msg_free.msg_type == "FREE"

    # 3. NeighborQueryMessage
    msg_nq = NeighborQueryMessage(sender_id=sender, receiver_id=receiver, tick=tick, position=target_cell)
    assert msg_nq.position == target_cell
    assert msg_nq.msg_type == "NEIGHBOR_QUERY"

    # 4. NeighborResponseMessage
    neighbors = [(Cell(0, 0), CellType.FREE, 2.5)]
    msg_nr = NeighborResponseMessage(sender_id=sender, receiver_id=receiver, tick=tick, neighbors=neighbors)
    assert msg_nr.neighbors == neighbors
    assert msg_nr.msg_type == "NEIGHBOR_RESPONSE"

    # 5. MoveMessage
    msg_m = MoveMessage(sender_id=sender, receiver_id=receiver, tick=tick, from_cell=Cell(0, 0), to_cell=Cell(0, 1))
    assert msg_m.from_cell == Cell(0, 0)
    assert msg_m.to_cell == Cell(0, 1)
    assert msg_m.msg_type == "MOVE"

    # 6. HUpdateMessage
    msg_hu = HUpdateMessage(sender_id=sender, receiver_id=receiver, tick=tick, cell=target_cell, value=5.5)
    assert msg_hu.cell == target_cell
    assert msg_hu.value == 5.5
    assert msg_hu.msg_type == "H_UPDATE"

    # 7. ReserveMessage
    msg_res = ReserveMessage(sender_id=sender, receiver_id=receiver, tick=tick, cell=target_cell, reserve_tick=11)
    assert msg_res.cell == target_cell
    assert msg_res.reserve_tick == 11
    assert msg_res.msg_type == "RESERVE"

    # 8. ClearedMessage
    msg_cl = ClearedMessage(sender_id=sender, receiver_id=receiver, tick=tick, signal=target_cell)
    assert msg_cl.signal == target_cell
    assert msg_cl.msg_type == "CLEARED"

    # 9. NewSignalMessage
    msg_ns = NewSignalMessage(sender_id=sender, receiver_id=receiver, tick=tick, location=target_cell)
    assert msg_ns.location == target_cell
    assert msg_ns.msg_type == "NEW_SIGNAL"

    # 10. TerminateMessage
    msg_term = TerminateMessage(sender_id=sender, receiver_id=receiver, tick=tick)
    assert msg_term.msg_type == "TERMINATE"
