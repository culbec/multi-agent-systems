import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIHorizontalSlider, UILabel


class PlaybackPanel:
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect):
        self.manager = manager
        self.rect = rect
        self.elements = []

        # Dimensions and margins
        y_offset = rect.y + 10
        x_offset = rect.x + 10
        width = rect.width - 20

        # We arrange the buttons in a nice horizontal row
        btn_w = 50
        btn_h = 30
        gap = 5

        # 1. Playback navigation buttons
        self.btn_restart = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (btn_w, btn_h)),
            text="<<",
            manager=manager,
            tool_tip_text="Jump to start",
        )
        x_offset += btn_w + gap

        self.btn_step_back = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (btn_w, btn_h)),
            text="<",
            manager=manager,
            tool_tip_text="Step back (Left Arrow)",
        )
        x_offset += btn_w + gap

        self.btn_play_pause = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (btn_w * 2, btn_h)),
            text="PLAY",
            manager=manager,
            tool_tip_text="Play / Pause (Space)",
        )
        x_offset += (btn_w * 2) + gap

        self.btn_step_forward = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (btn_w, btn_h)),
            text=">",
            manager=manager,
            tool_tip_text="Step forward (Right Arrow)",
        )
        x_offset += btn_w + gap

        self.btn_end = UIButton(
            relative_rect=pygame.Rect((x_offset, y_offset), (btn_w, btn_h)),
            text=">>",
            manager=manager,
            tool_tip_text="Jump to end",
        )
        x_offset += btn_w + 20

        self.elements.extend(
            [self.btn_restart, self.btn_step_back, self.btn_play_pause, self.btn_step_forward, self.btn_end]
        )

        # 2. Tick scrubber slider
        scrubber_w = width - (x_offset - rect.x - 10) - 200
        if scrubber_w < 100:
            scrubber_w = 200
        self.scrubber = UIHorizontalSlider(
            relative_rect=pygame.Rect((x_offset, y_offset + 5), (scrubber_w, 20)),
            start_value=0,
            value_range=(0, 100),
            manager=manager,
        )
        self.elements.append(self.scrubber)
        x_offset += scrubber_w + 10

        # 3. Tick indicator label
        self.lbl_tick = UILabel(
            relative_rect=pygame.Rect((x_offset, y_offset + 5), (150, 20)), text="Tick: 0 / 0", manager=manager
        )
        self.elements.append(self.lbl_tick)

        # Second row: Speed control slider and label
        y_offset += 40
        x_offset = rect.x + 10

        self.lbl_speed_title = UILabel(
            relative_rect=pygame.Rect((x_offset, y_offset), (150, 20)), text="Speed: 5 tps", manager=manager
        )
        self.elements.append(self.lbl_speed_title)
        x_offset += 160

        self.speed_slider = UIHorizontalSlider(
            relative_rect=pygame.Rect((x_offset, y_offset), (300, 20)),
            start_value=5,
            value_range=(1, 60),
            manager=manager,
        )
        self.elements.append(self.speed_slider)

        # Reset button in the bottom bar, placed on the right side of the speed controls
        self.btn_reset = UIButton(
            relative_rect=pygame.Rect((rect.x + width - 180, y_offset - 5), (170, 30)),
            text="RESET CONFIG",
            manager=manager,
            tool_tip_text="Reset simulation and edit parameters",
        )
        self.elements.append(self.btn_reset)

        # Initialize speed settings
        self.speed_tps = 5
        self.playing = False
        self.max_ticks = 0
        self.current_tick = 0

        self.disable_controls()

    def set_simulation_stats(self, max_ticks: int):
        self.max_ticks = max_ticks
        self.scrubber.value_range = (0, max_ticks)
        self.scrubber.set_current_value(0)
        self.lbl_tick.set_text(f"Tick: 0 / {max_ticks}")
        self.enable_controls()

    def update_tick(self, tick: int):
        self.current_tick = tick
        self.scrubber.set_current_value(tick)
        self.lbl_tick.set_text(f"Tick: {tick} / {self.max_ticks}")

    def update(self):
        """Update speed display and check slider values."""
        self.speed_tps = int(self.speed_slider.get_current_value())
        self.lbl_speed_title.set_text(f"Speed: {self.speed_tps} tps")

        # Update play button text based on status
        if self.playing:
            self.btn_play_pause.set_text("PAUSE")
        else:
            self.btn_play_pause.set_text("PLAY")

    def toggle_play(self):
        self.playing = not self.playing

    def disable_controls(self):
        """Disable buttons when no simulation is active."""
        for elem in self.elements:
            elem.disable()
        self.scrubber.disable()

    def enable_controls(self):
        """Enable buttons when a simulation is active."""
        for elem in self.elements:
            elem.enable()
        self.scrubber.enable()
