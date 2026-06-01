from src.sp2.domain.cell import Cell
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    FreeMessage,
    TerminateMessage,
)


def test_messages():
    sender = 1
    receiver = 2
    tick = 10
    target_cell = Cell(1, 2)

    # AssignMessage (Coordinator -> Rescue)
    msg = AssignMessage(sender_id=sender, receiver_id=receiver, tick=tick, target=target_cell)
    assert msg.sender_id == sender
    assert msg.receiver_id == receiver
    assert msg.tick == tick
    assert msg.target == target_cell
    assert msg.msg_type == "ASSIGN"

    # FreeMessage (Rescue -> Coordinator)
    msg_free = FreeMessage(sender_id=sender, receiver_id=receiver, tick=tick, agent_id=sender, position=target_cell)
    assert msg_free.agent_id == sender
    assert msg_free.position == target_cell
    assert msg_free.msg_type == "FREE"

    # ClearedMessage (Rescue -> peers + Coordinator)
    msg_cl = ClearedMessage(sender_id=sender, receiver_id=receiver, tick=tick, signal=target_cell)
    assert msg_cl.signal == target_cell
    assert msg_cl.msg_type == "CLEARED"

    # TerminateMessage (Coordinator -> Rescue)
    msg_term = TerminateMessage(sender_id=sender, receiver_id=receiver, tick=tick)
    assert msg_term.msg_type == "TERMINATE"
