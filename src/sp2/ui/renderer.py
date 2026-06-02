import math

import pygame

from src.sp2.defaults import (
    AGENT_COLORS_PALETTE,
    COLOR_BASE,
    COLOR_FREE,
    COLOR_GRID_LINE,
    COLOR_HIGHLIGHT_BLACK,
    COLOR_HIGHLIGHT_WHITE,
    COLOR_OBSTACLE,
    COLOR_OBSTACLE_HATCH,
    COLOR_RESERVATION_BORDER,
    COLOR_SIGNAL_ACTIVE,
    COLOR_SIGNAL_RESOLVED,
    MAX_CELL_SIZE,
    MIN_CELL_SIZE,
)


class GridRenderer:
    def __init__(self):
        # Palette colors
        self.colors = {
            "FREE": pygame.Color(COLOR_FREE),
            "OBSTACLE": pygame.Color(COLOR_OBSTACLE),
            "SIGNAL_ACTIVE": pygame.Color(COLOR_SIGNAL_ACTIVE),
            "SIGNAL_RESOLVED": pygame.Color(COLOR_SIGNAL_RESOLVED),
            "BASE": pygame.Color(COLOR_BASE),
            "GRID_LINE": pygame.Color(COLOR_GRID_LINE),
        }
        # Agent color palette
        self.agent_colors = [pygame.Color(c) for c in AGENT_COLORS_PALETTE]

        # Display toggles
        self.show_heatmap = False
        self.show_trails = True
        self.show_reservations = True
        self.show_grid = True

    def get_agent_color(self, agent_id: int, agent_count: int) -> pygame.Color:
        """Dynamically generates a distinct spectral hue gradient color for each agent."""
        if agent_count <= 1:
            hue = 0.0
        else:
            # Spread hue evenly across the full 360-degree color wheel
            hue = (agent_id / agent_count) * 360.0

        color = pygame.Color(0)
        # Use high saturation (85) and brightness/value (90) for vibrant, visible circles
        color.hsva = (hue, 85.0, 90.0, 100.0)
        return color

    def render(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        frame: dict,
        rows: int,
        cols: int,
        base_location: tuple[int, int],
        obstacle_coords: list[tuple[int, int]],
        tick: int,
        all_frames: list[dict],
        selected_agent_id: int | None = None,
    ) -> dict:
        """
        Renders the grid onto the specified surface area.
        Returns a dict mapping (row, col) -> rect of the cell, for mouse collision detection.
        """
        # Draw background of grid area
        pygame.draw.rect(surface, self.colors["FREE"], rect)

        # Calculate cell size
        avail_w, avail_h = rect.width, rect.height
        cell_size = min(avail_w // cols, avail_h // rows)
        cell_size = max(MIN_CELL_SIZE, min(cell_size, MAX_CELL_SIZE))

        # Center the grid in the allocated rect
        grid_w = cell_size * cols
        grid_h = cell_size * rows
        start_x = rect.x + (avail_w - grid_w) // 2
        start_y = rect.y + (avail_h - grid_h) // 2

        # Grid cell rectangles map
        cell_rects = {}

        # 1. Draw base cell background
        base_r, base_c = base_location

        # Determine active and resolved signals in this frame
        active_signals = set(frame["active_signals"])
        resolved_signals = set(frame["resolved_signals"]) - active_signals

        # Determine agent positions and active reservations in this frame
        agent_positions = {a["id"]: a["position"] for a in frame["agents"]}

        # Reservations are world state now (the Environment's reservation table,
        # Decision D1, Option A), not inter-agent messages. The Simulation
        # snapshots the cells reserved this tick into the frame before clearing
        # them, so the overlay reads them directly rather than scraping the log.
        reserved_cells = {(r, c) for r, c in frame.get("reservations", [])}

        # 2. Draw static cells: FREE, OBSTACLE
        obstacles_set = set(obstacle_coords)
        for r in range(rows):
            for c in range(cols):
                cell_rect = pygame.Rect(start_x + c * cell_size, start_y + r * cell_size, cell_size, cell_size)
                cell_rects[(r, c)] = cell_rect

                if (r, c) in obstacles_set:
                    pygame.draw.rect(surface, self.colors["OBSTACLE"], cell_rect)
                    # Draw a nice diagonal hatch pattern for obstacles
                    pygame.draw.line(
                        surface, pygame.Color(COLOR_OBSTACLE_HATCH), cell_rect.topleft, cell_rect.bottomright, 1
                    )
                else:
                    pygame.draw.rect(surface, self.colors["FREE"], cell_rect)

        # 3. Draw Heuristic Heatmap Overlay if enabled
        if self.show_heatmap and frame["heuristic_map"]:
            h_vals = list(frame["heuristic_map"].values())
            if h_vals:
                min_h, max_h = min(h_vals), max(h_vals)
                h_range = max_h - min_h
                for (r, c), h in frame["heuristic_map"].items():
                    if (r, c) in cell_rects and (r, c) not in obstacles_set:
                        # Normalize h-value between 0.0 and 1.0
                        norm = (h - min_h) / h_range if h_range > 0 else 0.0
                        # Color: blue (low h) to red (high h)
                        # We can interpolate R, G, B
                        red = int(255 * norm)
                        blue = int(255 * (1.0 - norm))
                        green = 0

                        # Draw semi-transparent overlay
                        overlay = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                        overlay.fill((red, green, blue, 120))  # 120 is alpha
                        surface.blit(overlay, cell_rects[(r, c)].topleft)

        # 4. Draw Trails if enabled
        if self.show_trails:
            # We draw lines representing trails for each agent up to the current tick
            agent_count = len(frame["agents"])
            for a_info in frame["agents"]:
                aid = a_info["id"]
                color = self.get_agent_color(aid, agent_count)
                # Reconstruct trail up to current tick
                trail_points = []
                for t in range(tick + 1):
                    if t < len(all_frames):
                        for pa in all_frames[t]["agents"]:
                            if pa["id"] == aid:
                                r, c = pa["position"]
                                cx = start_x + c * cell_size + cell_size // 2
                                cy = start_y + r * cell_size + cell_size // 2
                                trail_points.append((cx, cy))
                                break

                # Draw trail as semi-transparent connected lines
                if len(trail_points) >= 2:
                    # Draw line segments
                    for i in range(1, len(trail_points)):
                        p1, p2 = trail_points[i - 1], trail_points[i]
                        # Draw anti-aliased trail line
                        pygame.draw.line(surface, color, p1, p2, max(2, cell_size // 10))

        # 5. Draw BASE, SIGNAL (active/resolved)
        # Base
        base_rect = cell_rects[base_location]
        pygame.draw.rect(surface, self.colors["BASE"], base_rect)
        # Draw a little base symbol (e.g. nested square)
        pygame.draw.rect(surface, pygame.Color("#ffffff"), base_rect.inflate(-cell_size // 2, -cell_size // 2), 2)

        # Resolved signals
        for r, c in resolved_signals:
            if (r, c) in cell_rects:
                s_rect = cell_rects[(r, c)]
                pygame.draw.rect(surface, self.colors["SIGNAL_RESOLVED"], s_rect)
                # Draw checkmark or cross inside resolved signal
                pygame.draw.line(
                    surface, pygame.Color("#ffffff"), s_rect.center, (s_rect.right - 4, s_rect.top + 4), 2
                )
                pygame.draw.line(
                    surface, pygame.Color("#ffffff"), s_rect.center, (s_rect.left + 4, s_rect.center[1] + 2), 2
                )

        # Active signals (with pulsing animation using a sine wave alpha)
        pulse_val = abs(math.sin(pygame.time.get_ticks() / 300.0))
        glow_alpha = int(100 + 155 * pulse_val)
        # Which agent is assigned to each active signal (from the coordinator).
        signal_assignments = {(r, c): aid for r, c, aid in frame.get("signal_assignments", [])}
        agent_count = len(frame["agents"])
        badge_font = pygame.font.SysFont("Arial", max(8, int(cell_size * 0.26)), bold=True)
        for r, c in active_signals:
            if (r, c) in cell_rects:
                s_rect = cell_rects[(r, c)]
                # Draw solid red core
                pygame.draw.rect(surface, self.colors["SIGNAL_ACTIVE"], s_rect)
                # Draw glowing outer border/overlay
                glow_surf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                glow_surf.fill((231, 76, 60, glow_alpha))
                surface.blit(glow_surf, s_rect.topleft)

                # Badge the responding agent's id (in that agent's colour) so the
                # signal->agent assignment is readable from the board.
                assigned_aid = signal_assignments.get((r, c))
                if assigned_aid is not None:
                    badge_r = max(7, int(cell_size * 0.18))
                    bx, by = s_rect.right - badge_r - 2, s_rect.top + badge_r + 2
                    pygame.draw.circle(surface, self.get_agent_color(assigned_aid, agent_count), (bx, by), badge_r)
                    pygame.draw.circle(surface, pygame.Color(COLOR_HIGHLIGHT_BLACK), (bx, by), badge_r, 1)
                    badge_text = badge_font.render(str(assigned_aid), True, pygame.Color(COLOR_HIGHLIGHT_WHITE))
                    surface.blit(badge_text, badge_text.get_rect(center=(bx, by)))

        # 6. Draw yellow reservation borders if enabled
        if self.show_reservations:
            for r, c in reserved_cells:
                if (r, c) in cell_rects:
                    pygame.draw.rect(surface, pygame.Color(COLOR_RESERVATION_BORDER), cell_rects[(r, c)], 3)

        # 7. Draw Grid lines if enabled
        if self.show_grid:
            for r in range(rows + 1):
                y = start_y + r * cell_size
                pygame.draw.line(surface, self.colors["GRID_LINE"], (start_x, y), (start_x + grid_w, y))
            for c in range(cols + 1):
                x = start_x + c * cell_size
                pygame.draw.line(surface, self.colors["GRID_LINE"], (x, start_y), (x, start_y + grid_h))

        # 8. Draw AGENTS (filled circles with agent ID text)
        agent_count = len(frame["agents"])
        for a_info in frame["agents"]:
            aid = a_info["id"]
            r, c = a_info["position"]
            cx = start_x + c * cell_size + cell_size // 2
            cy = start_y + r * cell_size + cell_size // 2
            radius = int(cell_size * 0.4)
            color = self.get_agent_color(aid, agent_count)

            # Highlight selected agent with white outer ring
            if aid == selected_agent_id:
                pygame.draw.circle(surface, pygame.Color(COLOR_HIGHLIGHT_WHITE), (cx, cy), radius + 4, 3)

            pygame.draw.circle(surface, color, (cx, cy), radius)
            pygame.draw.circle(surface, pygame.Color(COLOR_HIGHLIGHT_BLACK), (cx, cy), radius, 1)

            # Draw agent ID text inside circle
            font_size = max(10, int(cell_size * 0.5))
            font = pygame.font.SysFont("Arial", font_size, bold=True)
            text_surf = font.render(str(aid), True, pygame.Color(COLOR_HIGHLIGHT_WHITE))
            text_rect = text_surf.get_rect(center=(cx, cy))
            surface.blit(text_surf, text_rect)

        return cell_rects
