import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIHorizontalSlider, UILabel, UITextEntryLine

from src.sp2.defaults import (
    DEFAULT_AGENT_COUNT,
    DEFAULT_COLS,
    DEFAULT_DYNAMIC_FREQUENCY,
    DEFAULT_INITIAL_SIGNALS,
    DEFAULT_MAX_TICKS,
    DEFAULT_OBSTACLE_DENSITY,
    DEFAULT_ROWS,
    DEFAULT_SEED,
)


class ConfigPanel:
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect):
        self.manager = manager
        self.rect = rect
        self.elements = []
        self.values = {}

        # We build the sidebar inside the specified rect area
        x_offset = rect.x + 10
        y_offset = rect.y + 10
        width = rect.width - 20

        # 1. Panel Header
        self.title = UILabel(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 30)), text="SIMULATION CONFIG", manager=manager
        )
        self.elements.append(self.title)
        y_offset += 40

        # Sliders helper
        def create_slider(name, label_text, min_v, max_v, default_v, step_v=1):
            if name == "dyn_frequency":
                lbl_val = f"{default_v / 10.0:.1f}"
            elif name == "density":
                lbl_val = f"{default_v}%"
            else:
                lbl_val = str(default_v)

            lbl = UILabel(
                relative_rect=pygame.Rect((x_offset, y_offset), (width, 20)),
                text=f"{label_text}: {lbl_val}",
                manager=manager,
            )
            y_of = y_offset + 22
            slider = UIHorizontalSlider(
                relative_rect=pygame.Rect((x_offset, y_of), (width, 20)),
                start_value=default_v,
                value_range=(min_v, max_v),
                manager=manager,
            )
            self.elements.append(lbl)
            self.elements.append(slider)
            self.values[name] = {"slider": slider, "label": lbl, "label_text": label_text, "type": type(default_v)}
            return y_of + 30

        y_offset = create_slider("rows", "Grid Rows", 5, 50, DEFAULT_ROWS)
        y_offset = create_slider("cols", "Grid Cols", 5, 50, DEFAULT_COLS)
        y_offset = create_slider("density", "Obstacle Density (%)", 0, 40, int(DEFAULT_OBSTACLE_DENSITY * 100))
        y_offset = create_slider("agents", "Rescue Agents", 1, 10, DEFAULT_AGENT_COUNT)
        y_offset = create_slider("signals", "Initial Signals", 1, 20, DEFAULT_INITIAL_SIGNALS)

        # For float:
        y_offset = create_slider(
            "dyn_frequency", "Dynamic Signal Freq", 0, 20, int(DEFAULT_DYNAMIC_FREQUENCY * 10)
        )  # Represented as 0.0 to 2.0 scaled by 10

        # Text input fields: Seed, Max Ticks
        lbl_seed = UILabel(relative_rect=pygame.Rect((x_offset, y_offset), (width, 20)), text="Seed:", manager=manager)
        y_offset += 22
        self.seed_entry = UITextEntryLine(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 30)), manager=manager
        )
        self.seed_entry.set_text(str(DEFAULT_SEED))
        self.elements.extend([lbl_seed, self.seed_entry])
        y_offset += 40

        lbl_ticks = UILabel(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 20)), text="Max Ticks:", manager=manager
        )
        y_offset += 22
        self.ticks_entry = UITextEntryLine(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 30)), manager=manager
        )
        self.ticks_entry.set_text(str(DEFAULT_MAX_TICKS))
        self.elements.extend([lbl_ticks, self.ticks_entry])
        y_offset += 50

        # Buttons
        self.generate_btn = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 40)), text="GENERATE & RUN", manager=manager
        )
        self.elements.append(self.generate_btn)
        y_offset += 50

        self.reset_btn = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 40)), text="RESET CONFIG", manager=manager
        )
        self.elements.append(self.reset_btn)
        y_offset += 50

        self.reload_btn = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (width, 40)),
            text="HOT RELOAD JSON",
            manager=manager,
            tool_tip_text="Manually trigger immediate reload from config file",
        )
        self.elements.append(self.reload_btn)

    def handle_event(self, event: pygame.Event):
        # Update slider label texts when sliding
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            for name, data in self.values.items():
                if event.ui_element == data["slider"]:
                    val = data["slider"].get_current_value()
                    if name == "dyn_frequency":
                        lbl_val = f"{val / 10.0:.1f}"
                    elif name == "density":
                        lbl_val = f"{val}%"
                    else:
                        lbl_val = str(val)
                    data["label"].set_text(f"{data['label_text']}: {lbl_val}")

    def get_config_dict(self) -> dict:
        """Extract config settings from UI controls."""
        rows = int(self.values["rows"]["slider"].get_current_value())
        cols = int(self.values["cols"]["slider"].get_current_value())
        density = float(self.values["density"]["slider"].get_current_value()) / 100.0
        agents = int(self.values["agents"]["slider"].get_current_value())
        signals = int(self.values["signals"]["slider"].get_current_value())
        dyn_freq = float(self.values["dyn_frequency"]["slider"].get_current_value()) / 10.0

        try:
            seed = int(self.seed_entry.get_text())
        except ValueError:
            seed = 42

        try:
            max_ticks = int(self.ticks_entry.get_text())
        except ValueError:
            max_ticks = 200

        return {
            "rows": rows,
            "cols": cols,
            "obstacle_density": density,
            "num_signals": signals,
            "agent_count": agents,
            "dynamic_signal_frequency": dyn_freq,
            "dynamic_signal_duration": 100,
            "max_ticks": max_ticks,
            "seed": seed,
        }

    def set_interactive(self, enabled: bool):
        """Grays out or enables inputs after generation."""
        for name, data in self.values.items():
            if enabled:
                data["slider"].enable()
            else:
                data["slider"].disable()

        if enabled:
            self.seed_entry.enable()
            self.ticks_entry.enable()
            self.generate_btn.enable()
            self.reload_btn.enable()
        else:
            self.seed_entry.disable()
            self.ticks_entry.disable()
            self.generate_btn.disable()
            self.reload_btn.disable()

    def reset_defaults(self):
        """Resets all sliders and entry fields to their original/default values."""
        defaults = {
            "rows": DEFAULT_ROWS,
            "cols": DEFAULT_COLS,
            "density": int(DEFAULT_OBSTACLE_DENSITY * 100),
            "agents": DEFAULT_AGENT_COUNT,
            "signals": DEFAULT_INITIAL_SIGNALS,
            "dyn_frequency": int(DEFAULT_DYNAMIC_FREQUENCY * 10),
        }
        for name, def_val in defaults.items():
            if name in self.values:
                data = self.values[name]
                data["slider"].set_current_value(def_val)
                # Update labels explicitly
                if name == "dyn_frequency":
                    lbl_val = f"{def_val / 10.0:.1f}"
                elif name == "density":
                    lbl_val = f"{def_val}%"
                else:
                    lbl_val = str(def_val)
                data["label"].set_text(f"{data['label_text']}: {lbl_val}")

        self.seed_entry.set_text(str(DEFAULT_SEED))
        self.ticks_entry.set_text(str(DEFAULT_MAX_TICKS))
