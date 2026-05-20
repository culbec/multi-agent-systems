import argparse
import json
import os

import pygame
import pygame_gui

from src.sp2.defaults import (
    COLOR_BG_DARK,
    COLOR_HUD_TEXT_MUTED,
    COLOR_INSTRUCTIONS_TEXT,
    DEFAULT_AGENT_COUNT,
    DEFAULT_BOTTOM_BAR_HEIGHT,
    DEFAULT_COLS,
    DEFAULT_DYNAMIC_FREQUENCY,
    DEFAULT_INITIAL_SIGNALS,
    DEFAULT_MAX_TICKS,
    DEFAULT_OBSTACLE_DENSITY,
    DEFAULT_ROWS,
    DEFAULT_SEED,
    DEFAULT_SIDEBAR_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)

# Adjust PYTHONPATH imports
from src.sp2.simulation import Simulation
from src.sp2.ui.controls import ConfigPanel
from src.sp2.ui.hud import HUD
from src.sp2.ui.playback import PlaybackPanel
from src.sp2.ui.renderer import GridRenderer
from src.sp2.utils.config_loader import load_any_config
from src.sp2.utils.grid_generator import generate_config


def run_headless(args, preloaded_config=None):
    """Runs the simulation in command-line only mode."""
    print("Running in headless mode...")

    if preloaded_config is not None:
        config = preloaded_config
    else:
        config = generate_config(
            rows=args.rows,
            cols=args.cols,
            obstacle_density=args.density,
            num_signals=args.signals,
            agent_count=args.agents,
            dynamic_signal_frequency=args.dyn_freq,
            dynamic_signal_duration=100,
            max_ticks=args.max_ticks,
            seed=args.seed,
        )

    sim = Simulation(config)
    print("Executing simulation ticks...")
    stats = sim.run()

    print("\n--- SIMULATION RESULTS ---")
    print(f"Total Ticks (Makespan): {stats['makespan']}")
    print(f"Total Steps Executed: {stats['total_steps']}")
    print(
        f"Signals Resolved: {stats['signals_resolved']} / {len(config.initial_signals) + len(config.dynamic_signal_stream)}"
    )
    print(f"Average Resolution Time: {stats['avg_resolution_time']:.2f} ticks")
    print(f"Mean Heuristic Change per Tick: {stats['mean_heuristic_change']:.4f}")

    print("\nPer-Agent Breakdowns:")
    for a in stats["per_agent"]:
        print(
            f"  Agent #{a['id']}: Steps={a['steps']}, Resolved={a['signals_resolved']}, Waits={a['wait_ticks']}, Idle Ratio={a['idle_ratio']:.2%}"
        )

    # Serialize frames to file if output is specified
    output_file = args.output
    if output_file:
        print(f"\nSaving replay frames to {output_file}...")
        serializable_frames = []
        for f in sim.frames:
            s_frame = f.copy()
            s_frame["heuristic_map"] = [[k[0], k[1], v] for k, v in f["heuristic_map"].items()]
            serializable_frames.append(s_frame)

        with open(output_file, "w") as f:
            json.dump(
                {
                    "config": {
                        "rows": config.rows,
                        "cols": config.cols,
                        "obstacle_coords": config.obstacle_coords,
                        "base_location": config.base_location,
                        "agent_count": config.agent_count,
                        "seed": config.seed,
                    },
                    "stats": stats,
                    "frames": serializable_frames,
                },
                f,
                indent=2,
            )
        print("Save completed successfully.")


def run_gui(preloaded_config=None, preloaded_params=None, config_path="", last_config_mtime=0.0):
    """Launches the full Pygame visual interface."""
    pygame.init()
    pygame.display.set_caption("SP2 - Disaster Grid Response System Replay")

    # Screen size
    screen_w, screen_h = DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
    screen = pygame.display.set_surface = pygame.display.set_mode((screen_w, screen_h))

    clock = pygame.time.Clock()
    manager = pygame_gui.UIManager((screen_w, screen_h))

    # Preload default Noto Sans bold 14pt font to prevent runtime layout lag and warnings
    manager.preload_fonts([{"name": "noto_sans", "point_size": 14, "style": "bold", "antialiased": 1}])

    # 1. Define layout areas
    # Config sidebar (right-most)
    sidebar_w = DEFAULT_SIDEBAR_WIDTH
    sidebar_rect = pygame.Rect(screen_w - sidebar_w, 0, sidebar_w, screen_h)

    # Playback panel (bottom bar)
    playback_h = DEFAULT_BOTTOM_BAR_HEIGHT
    playback_rect = pygame.Rect(0, screen_h - playback_h, screen_w - sidebar_w, playback_h)

    # HUD panel
    hud_rect = pygame.Rect(screen_w - sidebar_w, 0, sidebar_w, screen_h)

    # Grid rendering canvas
    grid_rect = pygame.Rect(0, 0, screen_w - sidebar_w, screen_h - playback_h)

    # 2. Instantiate UI Components
    config_panel = ConfigPanel(manager, sidebar_rect)
    playback_panel = PlaybackPanel(manager, playback_rect)
    hud = HUD(manager, hud_rect)

    # Initially hide HUD elements, as we start in CONFIG state
    hud.panel.hide()

    renderer = GridRenderer()

    # Simulation and Playback states
    class UIState:
        CONFIG = 0
        RUNNING = 1
        REPLAY = 2

    current_state = UIState.CONFIG

    config = preloaded_config
    sim = None
    stats = None
    frames = []

    selected_agent_id = None
    current_tick = 0
    last_tick_update_time = 0
    cell_rects = {}

    # Track previous state to optimize and prevent constant text updates that break scrolling
    last_rendered_tick = -1
    last_selected_agent_id = -1

    # Track config check timer for hot-reloading (once every 500ms to avoid system call thrashing)
    last_config_check_time = 0.0

    # Helper function to apply parameters to GUI panel
    def apply_gui_params(params):
        defaults = {
            "rows": params["rows"],
            "cols": params["cols"],
            "density": int(params["obstacle_density"] * 100),
            "agents": params["agent_count"],
            "signals": params["num_signals"],
            "dyn_frequency": int(params["dynamic_signal_frequency"] * 10),
        }
        for name, val in defaults.items():
            if name in config_panel.values:
                data = config_panel.values[name]
                data["slider"].set_current_value(val)
                if name == "dyn_frequency":
                    lbl_val = f"{val / 10.0:.1f}"
                elif name == "density":
                    lbl_val = f"{val}%"
                else:
                    lbl_val = str(val)
                data["label"].set_text(f"{data['label_text']}: {lbl_val}")

        config_panel.seed_entry.set_text(str(params["seed"]))
        config_panel.ticks_entry.set_text(str(params["max_ticks"]))

    # Apply preloaded parameters to GUI if they exist
    if preloaded_params is not None:
        apply_gui_params(preloaded_params)

    running_loop = True
    while running_loop:
        time_delta = clock.tick(60) / 1000.0

        # Determine background color
        screen.fill(pygame.Color(COLOR_BG_DARK))

        # Check for config file modification (Hot Reloading)
        if config_path and os.path.exists(config_path):
            now = pygame.time.get_ticks()
            if now - last_config_check_time >= 500.0:  # Check every 500ms
                last_config_check_time = now
                try:
                    mtime = os.path.getmtime(config_path)
                    if mtime > last_config_mtime:
                        print(f"[HOT RELOAD] Config change detected on {config_path}! Reloading...")
                        last_config_mtime = mtime

                        # Reload the configuration
                        new_config, new_params = load_any_config(config_path)

                        # Reset current simulation state completely
                        playback_panel.playing = False
                        playback_panel.disable_controls()
                        hud.panel.hide()

                        # Clear current simulation state
                        config = None
                        sim = None
                        stats = None
                        frames = []
                        current_tick = 0
                        selected_agent_id = None
                        last_rendered_tick = -1
                        last_selected_agent_id = -1

                        if new_config is not None:
                            # It's a concrete config layout - immediately load and replay it
                            config = new_config
                            current_state = UIState.CONFIG  # Triggers automatic simulation run on next loop turn
                        else:
                            # It's a parameter configuration - apply params and return to interactive CONFIG screen
                            apply_gui_params(new_params)

                            config_panel.title.show()
                            for data in config_panel.values.values():
                                data["slider"].show()
                                data["label"].show()
                            config_panel.seed_entry.show()
                            config_panel.ticks_entry.show()
                            config_panel.generate_btn.show()
                            config_panel.set_interactive(True)

                            current_state = UIState.CONFIG
                except Exception as e:
                    print(f"[HOT RELOAD ERROR] Failed to reload config: {e}")

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running_loop = False

            # Let manager process events first
            manager.process_events(event)

            # 1. Configuration Panel events
            if current_state == UIState.CONFIG:
                config_panel.handle_event(event)

                # Check for manual "HOT RELOAD JSON" button click
                is_manual_reload = (
                    event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == config_panel.reload_btn
                )
                if is_manual_reload and config_path and os.path.exists(config_path):
                    print(f"[MANUAL HOT RELOAD] Reloading from {config_path}...")
                    try:
                        last_config_mtime = os.path.getmtime(config_path)
                        new_config, new_params = load_any_config(config_path)
                        if new_config is not None:
                            config = new_config
                            # Re-trigger concrete load on next loop
                        else:
                            apply_gui_params(new_params)
                    except Exception as e:
                        print(f"[MANUAL HOT RELOAD ERROR] Failed: {e}")

                # Check for "RESET" button click to restore default values
                if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == config_panel.reset_btn:
                    config_panel.reset_defaults()

                # Check for "GENERATE" button click (or start with preloaded concrete config)
                is_generate_clicked = (
                    event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == config_panel.generate_btn
                )

                # If we preloaded a concrete config, we can automatically trigger simulation generation
                if is_generate_clicked or (config is not None and len(frames) == 0):
                    current_state = UIState.RUNNING

                    # Temporarily draw a "Running..." screen
                    screen.fill(pygame.Color(COLOR_BG_DARK))
                    font = pygame.font.SysFont("Arial", 36, bold=True)
                    text_surf = font.render("RUNNING SIMULATION...", True, pygame.Color("#ffffff"))
                    text_rect = text_surf.get_rect(center=(screen_w // 2, screen_h // 2))
                    screen.blit(text_surf, text_rect)
                    pygame.display.flip()

                    if config is None:
                        # Read parameters from sliders/entries
                        params = config_panel.get_config_dict()
                        config = generate_config(
                            rows=params["rows"],
                            cols=params["cols"],
                            obstacle_density=params["obstacle_density"],
                            num_signals=params["num_signals"],
                            agent_count=params["agent_count"],
                            dynamic_signal_frequency=params["dynamic_signal_frequency"],
                            dynamic_signal_duration=params["dynamic_signal_duration"],
                            max_ticks=params["max_ticks"],
                            seed=params["seed"],
                        )

                    # Run simulation
                    sim = Simulation(config)
                    stats = sim.run()
                    frames = sim.frames

                    # Configure playback controls
                    current_tick = 0
                    playback_panel.set_simulation_stats(len(frames) - 1)
                    playback_panel.playing = False

                    # Hide configuration panel and show HUD panel
                    config_panel.title.hide()
                    for data in config_panel.values.values():
                        data["slider"].hide()
                        data["label"].hide()
                    config_panel.seed_entry.hide()
                    config_panel.ticks_entry.hide()
                    config_panel.generate_btn.hide()

                    hud.panel.show()
                    hud.update_stats(
                        tick=0,
                        max_ticks=len(frames) - 1,
                        current_makespan=0,
                        cumulative_steps=0,
                        resolved_signals_count=0,
                        total_signals_count=len(config.initial_signals) + len(config.dynamic_signal_stream),
                        termination_reason=stats.get("termination_reason", ""),
                    )
                    hud.update_messages(frames[0]["messages_this_tick"])

                    last_rendered_tick = 0
                    last_selected_agent_id = -1

                    current_state = UIState.REPLAY

            # 2. Replay & Playback Panel events
            elif current_state == UIState.REPLAY:
                # Handle reset button click from either the config panel or bottom playback bar
                if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element in (
                    config_panel.reset_btn,
                    playback_panel.btn_reset,
                ):
                    # Return to config state
                    playback_panel.playing = False
                    playback_panel.disable_controls()

                    hud.panel.hide()

                    # Show config elements again
                    config_panel.title.show()
                    for data in config_panel.values.values():
                        data["slider"].show()
                        data["label"].show()
                    config_panel.seed_entry.show()
                    config_panel.ticks_entry.show()
                    config_panel.generate_btn.show()
                    config_panel.set_interactive(True)

                    current_state = UIState.CONFIG
                    config = None
                    sim = None
                    stats = None
                    frames = []
                    current_tick = 0
                    selected_agent_id = None
                    last_rendered_tick = -1
                    last_selected_agent_id = -1
                    continue

                # Handle playback button events
                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == playback_panel.btn_restart:
                        current_tick = 0
                        playback_panel.playing = False
                    elif event.ui_element == playback_panel.btn_step_back:
                        current_tick = max(0, current_tick - 1)
                        playback_panel.playing = False
                    elif event.ui_element == playback_panel.btn_play_pause:
                        playback_panel.toggle_play()
                    elif event.ui_element == playback_panel.btn_step_forward:
                        current_tick = min(len(frames) - 1, current_tick + 1)
                        playback_panel.playing = False
                    elif event.ui_element == playback_panel.btn_end:
                        current_tick = len(frames) - 1
                        playback_panel.playing = False

                # Handle manual scrubber dragging
                if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED and event.ui_element == playback_panel.scrubber:
                    current_tick = int(playback_panel.scrubber.get_current_value())

                # Handle clicks on the grid canvas to select agents
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mpos = event.pos
                    clicked_agent = None
                    for (r, c), r_rect in cell_rects.items():
                        if r_rect.collidepoint(mpos):
                            # Check if an agent is here in current frame
                            for a_info in frames[current_tick]["agents"]:
                                if a_info["position"] == (r, c):
                                    clicked_agent = a_info["id"]
                                    break
                    selected_agent_id = clicked_agent

                # Keyboard shortcuts for replay
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        playback_panel.toggle_play()
                    elif event.key == pygame.K_LEFT:
                        current_tick = max(0, current_tick - 1)
                        playback_panel.playing = False
                    elif event.key == pygame.K_RIGHT:
                        current_tick = min(len(frames) - 1, current_tick + 1)
                        playback_panel.playing = False
                    elif event.key == pygame.K_HOME:
                        current_tick = 0
                        playback_panel.playing = False
                    elif event.key == pygame.K_END:
                        current_tick = len(frames) - 1
                        playback_panel.playing = False
                    elif event.key == pygame.K_EQUALS or event.key == pygame.K_KP_PLUS:
                        playback_panel.speed_slider.set_current_value(min(60, playback_panel.speed_tps + 2))
                    elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                        playback_panel.speed_slider.set_current_value(max(1, playback_panel.speed_tps - 2))
                    elif event.key == pygame.K_h:
                        renderer.show_heatmap = not renderer.show_heatmap
                    elif event.key == pygame.K_t:
                        renderer.show_trails = not renderer.show_trails
                    elif event.key == pygame.K_r:
                        renderer.show_reservations = not renderer.show_reservations
                    elif event.key == pygame.K_g:
                        renderer.show_grid = not renderer.show_grid
                    elif event.key == pygame.K_m:
                        hud.toggle_message_log()

        # Update manager state
        manager.update(time_delta)

        # Replay logic: auto-advance frames based on tps speed
        if current_state == UIState.REPLAY:
            playback_panel.update()

            if playback_panel.playing:
                now = pygame.time.get_ticks()
                delay_ms = 1000.0 / playback_panel.speed_tps
                if now - last_tick_update_time >= delay_ms:
                    if current_tick < len(frames) - 1:
                        current_tick += 1
                    else:
                        # Auto pause at the end
                        playback_panel.playing = False
                    last_tick_update_time = now

            playback_panel.update_tick(current_tick)

            # Render grid and retrieve current cell rectangles
            curr_frame = frames[current_tick]
            cell_rects = renderer.render(
                surface=screen,
                rect=grid_rect,
                frame=curr_frame,
                rows=config.rows,
                cols=config.cols,
                base_location=config.base_location,
                obstacle_coords=config.obstacle_coords,
                tick=current_tick,
                all_frames=frames,
                selected_agent_id=selected_agent_id,
            )

            # Draw overlay instructions in replay mode
            font_small = pygame.font.SysFont("Arial", 14)
            shortcuts_str = "[H] Heatmap  [T] Trails  [R] Reservations  [G] Grid  [M] Message Log  [Space] Play/Pause"
            sc_text = font_small.render(shortcuts_str, True, pygame.Color(COLOR_HUD_TEXT_MUTED))
            screen.blit(sc_text, (20, 15))

            # Update HUD contents only when current_tick or selected_agent_id actually changes
            if current_tick != last_rendered_tick or selected_agent_id != last_selected_agent_id:
                # Count resolved signals up to current tick
                resolved_count = 0
                for sig in sim.environment.resolved_signals:
                    if sig.resolved_at_tick is not None and sig.resolved_at_tick <= current_tick:
                        resolved_count += 1

                # Calculate cumulative steps taken up to current tick
                cumulative_steps = 0
                if current_tick > 0 and len(frames) > 1:
                    # Sum up steps for each agent by tracking changes in position
                    for aid in range(len(curr_frame["agents"])):
                        agent_steps = 0
                        for t in range(1, current_tick + 1):
                            prev_pos = frames[t - 1]["agents"][aid]["position"]
                            curr_pos = frames[t]["agents"][aid]["position"]
                            if curr_pos != prev_pos:
                                agent_steps += 1
                        cumulative_steps += agent_steps

                # Calculate makespan up to current tick
                current_makespan = 0
                for sig in sim.environment.resolved_signals:
                    if sig.resolved_at_tick is not None and sig.resolved_at_tick <= current_tick:
                        current_makespan = max(current_makespan, sig.resolved_at_tick)

                total_signals = len(config.initial_signals) + len(config.dynamic_signal_stream)
                hud.update_stats(
                    tick=current_tick,
                    max_ticks=len(frames) - 1,
                    current_makespan=current_makespan,
                    cumulative_steps=cumulative_steps,
                    resolved_signals_count=resolved_count,
                    total_signals_count=total_signals,
                    termination_reason=stats.get("termination_reason", ""),
                )
                hud.update_agent_detail(selected_agent_id, curr_frame, stats, renderer.agent_colors)
                hud.update_messages(curr_frame["messages_this_tick"])

                last_rendered_tick = current_tick
                last_selected_agent_id = selected_agent_id

        elif current_state == UIState.CONFIG:
            # Render empty/clean grid instructions in config mode
            font = pygame.font.SysFont("Arial", 24)
            inst_surf = font.render(
                "Adjust parameters on the right, then click GENERATE", True, pygame.Color(COLOR_INSTRUCTIONS_TEXT)
            )
            inst_rect = inst_surf.get_rect(center=(grid_rect.centerx, grid_rect.centery))
            screen.blit(inst_surf, inst_rect)
            playback_panel.disable_controls()

        # Draw UI manager elements on top
        manager.draw_ui(screen)

        # Refresh display
        pygame.display.flip()

    pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="SP2 - Disaster Grid Response System Simulation & Replay")
    parser.add_argument(
        "--config",
        type=str,
        default="src/sp2/data/config.json",
        help="Path to JSON config file to preload parameters or concrete layouts (default: src/sp2/data/config.json)",
    )
    parser.add_argument("--headless", action="store_true", help="Runs simulation without graphical user interface")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help=f"Grid rows (default: {DEFAULT_ROWS})")
    parser.add_argument("--cols", type=int, default=DEFAULT_COLS, help=f"Grid columns (default: {DEFAULT_COLS})")
    parser.add_argument(
        "--agents",
        type=int,
        default=DEFAULT_AGENT_COUNT,
        help=f"Number of rescue agents (default: {DEFAULT_AGENT_COUNT})",
    )
    parser.add_argument(
        "--signals",
        type=int,
        default=DEFAULT_INITIAL_SIGNALS,
        help=f"Number of initial signals (default: {DEFAULT_INITIAL_SIGNALS})",
    )
    parser.add_argument(
        "--density",
        type=float,
        default=DEFAULT_OBSTACLE_DENSITY,
        help=f"Obstacle density from 0.0 to 0.4 (default: {DEFAULT_OBSTACLE_DENSITY})",
    )
    parser.add_argument(
        "--dyn-freq",
        type=float,
        default=DEFAULT_DYNAMIC_FREQUENCY,
        help=f"Dynamic signal average frequency (default: {DEFAULT_DYNAMIC_FREQUENCY})",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"RNG seed (default: {DEFAULT_SEED})")
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=DEFAULT_MAX_TICKS,
        help=f"Maximum simulation ticks (default: {DEFAULT_MAX_TICKS})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="src/sp2/data/replay_frames.json",
        help="JSON file path to save simulation replay frames (default: src/sp2/data/replay_frames.json)",
    )

    args = parser.parse_args()

    # Preload configuration if specified
    preloaded_config = None
    preloaded_params = None
    config_path = ""
    last_config_mtime = 0.0

    if args.config and os.path.exists(args.config):
        print(f"Preloading configuration from {args.config}...")
        config_path = args.config
        last_config_mtime = os.path.getmtime(config_path)
        preloaded_config, preloaded_params = load_any_config(config_path)

    if args.headless:
        run_headless(args, preloaded_config=preloaded_config)
    else:
        run_gui(
            preloaded_config=preloaded_config,
            preloaded_params=preloaded_params,
            config_path=config_path,
            last_config_mtime=last_config_mtime,
        )


if __name__ == "__main__":
    main()
