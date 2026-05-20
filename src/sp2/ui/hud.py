import pygame
import pygame_gui
from pygame_gui.elements import UILabel, UIPanel, UITextBox


class HUD:
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect):
        self.manager = manager
        self.rect = rect
        self.show_messages = True

        # We put the HUD in a nice transparent panel
        self.panel = UIPanel(relative_rect=rect, starting_height=1, manager=manager)

        # Stats labels
        self.lbl_makespan = UILabel(
            relative_rect=pygame.Rect((10, 10), (rect.width - 20, 20)),
            text="Makespan: 0    Total Steps: 0",
            manager=manager,
            container=self.panel,
        )
        self.lbl_signals = UILabel(
            relative_rect=pygame.Rect((10, 30), (rect.width - 20, 20)),
            text="Signals: 0/0 resolved",
            manager=manager,
            container=self.panel,
        )
        self.lbl_tick_stats = UILabel(
            relative_rect=pygame.Rect((10, 50), (rect.width - 20, 20)),
            text="Tick: 0 / 0",
            manager=manager,
            container=self.panel,
        )

        # Agent detail subtitle / container
        self.lbl_agent_detail_title = UILabel(
            relative_rect=pygame.Rect((10, 80), (rect.width - 20, 20)),
            text="Agent Detail (Click on grid agent)",
            manager=manager,
            container=self.panel,
        )
        self.txt_agent_detail = UITextBox(
            relative_rect=pygame.Rect((10, 100), (rect.width - 20, 110)),
            html_text="Select an agent to see details.",
            manager=manager,
            container=self.panel,
        )

        # Message Log Area (bottom of panel, scrollable)
        self.lbl_messages_title = UILabel(
            relative_rect=pygame.Rect((10, 215), (rect.width - 20, 20)),
            text="Message Log [Toggle: M]",
            manager=manager,
            container=self.panel,
        )
        self.txt_message_log = UITextBox(
            relative_rect=pygame.Rect((10, 235), (rect.width - 20, rect.height - 245)),
            html_text="Run simulation to see messages.",
            manager=manager,
            container=self.panel,
        )

    def update_stats(
        self,
        tick: int,
        max_ticks: int,
        current_makespan: int,
        cumulative_steps: int,
        resolved_signals_count: int,
        total_signals_count: int,
        termination_reason: str = "",
    ):
        self.lbl_makespan.set_text(f"Makespan: {current_makespan}    Steps: {cumulative_steps}")
        self.lbl_signals.set_text(f"Signals: {resolved_signals_count}/{total_signals_count} resolved")

        reason_suffix = f" ({termination_reason})" if termination_reason else ""
        self.lbl_tick_stats.set_text(f"Tick: {tick} / {max_ticks}{reason_suffix}")

    def update_agent_detail(self, agent_id: int | None, frame: dict, stats: dict, colors_ref: dict):
        if agent_id is None:
            self.txt_agent_detail.set_text("Select an agent to see details.")
            return

        # Find agent info in current frame
        agent_info = None
        for a in frame["agents"]:
            if a["id"] == agent_id:
                agent_info = a
                break

        if agent_info is None:
            self.txt_agent_detail.set_text("Select an agent to see details.")
            return

        # Find per-agent stats
        agent_stats = None
        for a_s in stats.get("per_agent", []):
            if a_s["id"] == agent_id:
                agent_stats = a_s
                break

        steps = agent_stats.get("steps", 0) if agent_stats else 0
        resolved = agent_stats.get("signals_resolved", 0) if agent_stats else 0

        html = f"""
        <b>Agent #{agent_id}</b><br>
        Position: {agent_info["position"]}<br>
        Target: {agent_info["target"] if agent_info["target"] else "None"}<br>
        State: {agent_info["state"]}<br>
        Steps: {steps}<br>
        Signals Resolved: {resolved}
        """
        self.txt_agent_detail.set_text(html)

    def update_messages(self, messages: list[dict]):
        if not self.show_messages:
            self.txt_message_log.set_text("Message log hidden.")
            return

        if not messages:
            self.txt_message_log.set_text("No messages sent this tick.")
            return

        html_lines = []
        for m in messages[:50]:  # Limit to 50 for performance
            sender = m["sender"]
            receiver = m["receiver"]
            mtype = m["type"]

            # Formulate clean logs
            sender_str = (
                f"Rescue#{sender}"
                if sender >= 0
                else ("Env" if sender == -1 else "Coord" if sender == -2 else "Unknown")
            )
            receiver_str = (
                f"Rescue#{receiver}"
                if receiver >= 0
                else ("Broadcast" if receiver == -1 else "Coord" if receiver == -2 else "Unknown")
            )

            # Simple description of payload
            payload_str = ""
            for k, v in m["payload"].items():
                payload_str += f" {k}={v}"

            line = f"<b>{sender_str}</b> -> {receiver_str}: <b>{mtype}</b>{payload_str}"
            html_lines.append(line)

        self.txt_message_log.set_text("<br>".join(html_lines))

    def toggle_message_log(self):
        self.show_messages = not self.show_messages
        if self.show_messages:
            self.txt_message_log.show()
            self.lbl_messages_title.show()
        else:
            self.txt_message_log.hide()
            self.lbl_messages_title.hide()
