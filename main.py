#!/usr/bin/env python3
"""
PHYSICS SANDBOX  -  draw lines, blocks and balls, then press  Physics<?>
to see every force as an arrow with real numbers and equations.

Install:  pip install pygame pymunk
Run:      python physics_sandbox.py

Mouse
  Select tool : drag objects around / throw them
  Line tool   : drag to draw a fixed ramp / wall
  Block tool  : click for a 1 m block, or drag a rectangle
  Ball tool   : click for a 1 m ball, or drag out a radius
  Erase tool  : click an object to delete it
Keys
  Everything is FROZEN until you press Physics<?> (or P); F11 = fullscreen
  M hide/show the menu | I hide/show the equations card
  SPACE pause | P physics on/off | +/- weight of selected | DEL delete selected
  G change gravity | C clear | 1-5 difficulty (while physics view is on)
Scale: 50 pixels = 1 metre.  Density is in kg per m^2 (2-D world).
"""
import math
import sys

import pygame
import pymunk
from pymunk import Vec2d

W, H = 1280, 760
LEFT = 34                       # width of the spiral-binding strip
PANEL_W = 236
PPM = 50.0                      # pixels per metre
FLOOR_H = 30
FLOOR_Y = H - FLOOR_H
SUB = 4                         # physics sub-steps per frame
FPS = 60

GRAVITIES = [("Earth", 9.81), ("Moon", 1.62), ("Mars", 3.71),
             ("Jupiter", 24.79), ("Zero-G", 0.0)]
LEVELS = ["Basic", "Intermediate", "Advanced", "Expert", "Genius"]

PAPER = (251, 248, 236)
GRID_MINOR = (214, 230, 240)
GRID_MAJOR = (178, 205, 228)
INK = (36, 42, 78)
INK_SOFT = (96, 104, 140)
CARD = (246, 240, 216)
CARD_EDGE = (120, 112, 90)
MARGIN_RED = (232, 130, 130)
HILITE = (255, 226, 110)
WHITE = INK                     # (old name) default text colour is now ink
C_GRAV = (205, 35, 35)
C_NORM = (15, 140, 70)
C_FRIC = (215, 110, 0)
C_VEL = (15, 105, 200)
C_NET = (190, 30, 150)
C_MOM = (105, 55, 185)


# --------------------------------------------------------------------------- UI
class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, surf, font, active=False, label=None, active_col=HILITE):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        col = active_col if active else ((255, 242, 200) if hover else (253, 250, 238))
        shadow = self.rect.move(2, 2)
        pygame.draw.rect(surf, (200, 190, 160), shadow, border_radius=7)
        pygame.draw.rect(surf, col, self.rect, border_radius=7)
        pygame.draw.rect(surf, INK, self.rect, 2, border_radius=7)
        t = font.render(label or self.label, True, INK)
        surf.blit(t, t.get_rect(center=self.rect.center))


def draw_hamburger(surf, rect):
    for i in range(3):
        y = rect.y + 11 + i * 9
        pygame.draw.line(surf, INK, (rect.x + 9, y), (rect.right - 9, y), 3)


def draw_chevron(surf, rect, direction):
    cx, cy = rect.center
    d = {"left": [(cx + 4, cy - 8), (cx - 5, cy), (cx + 4, cy + 8)],
         "up": [(cx - 8, cy + 4), (cx, cy - 5), (cx + 8, cy + 4)],
         "down": [(cx - 8, cy - 4), (cx, cy + 5), (cx + 8, cy - 4)]}[direction]
    pygame.draw.lines(surf, INK, False, d, 3)


class Slider:
    def __init__(self, x, y, w, lo, hi, val, label, fmt="{:.2f}", step=None):
        self.rect = pygame.Rect(x, y + 26, w, 8)
        self.lo, self.hi, self.val = lo, hi, val
        self.label, self.fmt, self.step = label, fmt, step
        self.x, self.y = x, y

    def hit(self, pos):
        return self.rect.inflate(18, 28).collidepoint(pos)

    def set_from_mouse(self, mx):
        t = min(1.0, max(0.0, (mx - self.rect.x) / self.rect.w))
        v = self.lo + t * (self.hi - self.lo)
        if self.step:
            v = round(v / self.step) * self.step
        self.val = v

    def draw(self, surf, font):
        txt = font.render(f"{self.label}: {self.fmt.format(self.val)}", True, INK)
        surf.blit(txt, (self.x, self.y))
        pygame.draw.rect(surf, (205, 198, 175), self.rect, border_radius=4)
        pygame.draw.rect(surf, INK, self.rect, 2, border_radius=4)
        t = (self.val - self.lo) / (self.hi - self.lo)
        hx = self.rect.x + t * self.rect.w
        pygame.draw.circle(surf, HILITE, (hx, self.rect.centery), 10)
        pygame.draw.circle(surf, INK, (hx, self.rect.centery), 10, 2)


def draw_arrow(surf, color, start, vec, width=3):
    L = vec.length
    if L < 3:
        return
    end = start + vec
    pygame.draw.line(surf, color, (start.x, start.y), (end.x, end.y), width)
    d = vec / L
    n = Vec2d(-d.y, d.x)
    head = min(13, L * 0.5)
    pts = [end, end - d * head + n * head * 0.5, end - d * head - n * head * 0.5]
    pygame.draw.polygon(surf, color, [(p.x, p.y) for p in pts])


def force_to_pixels(F):
    """Arrow length grows with sqrt(force) so both tiny and huge forces stay visible."""
    L = F.length
    if L < 0.05:
        return Vec2d(0, 0)
    return F / L * min(170.0, 9.0 * math.sqrt(L))


def draw_shrimp(surf, cx, cy, s=1.0):
    """A small cartoon shrimp, centred around (cx, cy)."""
    body, dark, light = (255, 150, 120), (150, 55, 45), (255, 205, 180)
    pts = []
    for i in range(8):
        t = i / 7
        pts.append((cx - 34 * s + t * 62 * s,
                    cy - 4 * s - math.sin(t * math.pi) * 15 * s + t * t * 17 * s))
    hx, hy = pts[0]
    # antennae
    for dy in (-14, -6):
        pygame.draw.lines(surf, dark, False,
                          [(hx - 4 * s, hy - 4 * s), (hx - 14 * s, hy + dy * s),
                           (hx - 30 * s, hy + (dy - 4) * s)], 2)
    # little legs
    for p in pts[1:6]:
        pygame.draw.line(surf, dark, (p[0], p[1] + 5 * s), (p[0] - 5 * s, p[1] + 13 * s), 2)
    # tail fan
    tx, ty = pts[-1]
    for ang in (-35, 0, 35):
        a = math.radians(ang + 20)
        pygame.draw.polygon(surf, light, [
            (tx, ty), (tx + math.cos(a - 0.35) * 16 * s, ty + math.sin(a - 0.35) * 16 * s),
            (tx + math.cos(a + 0.35) * 16 * s, ty + math.sin(a + 0.35) * 16 * s)])
        pygame.draw.polygon(surf, dark, [
            (tx, ty), (tx + math.cos(a - 0.35) * 16 * s, ty + math.sin(a - 0.35) * 16 * s),
            (tx + math.cos(a + 0.35) * 16 * s, ty + math.sin(a + 0.35) * 16 * s)], 1)
    # body segments, tail -> head
    for i in range(7, -1, -1):
        r = (11 - i * 0.9) * s
        pygame.draw.circle(surf, body, pts[i], r)
        pygame.draw.circle(surf, dark, pts[i], r, 1)
    # rostrum + eye
    pygame.draw.polygon(surf, dark, [(hx - 8 * s, hy - 7 * s), (hx - 20 * s, hy - 11 * s), (hx - 6 * s, hy - 2 * s)])
    pygame.draw.circle(surf, (255, 255, 255), (hx - 4 * s, hy - 4 * s), 3.6 * s)
    pygame.draw.circle(surf, (10, 10, 10), (hx - 5 * s, hy - 4 * s), 1.9 * s)


# -------------------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Physics Sandbox")
        self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        body_fonts = "segoeui,helveticaneue,helvetica,arial,dejavusans,freesans"
        hand_fonts = "segoeprint,bradleyhand,chalkboardse,comicsansms,dejavusans"
        self.font = pygame.font.SysFont(body_fonts, 18)
        self.big = pygame.font.SysFont(body_fonts, 21, bold=True)
        self.hand = pygame.font.SysFont(hand_fonts, 24, bold=True)
        self.small = pygame.font.SysFont(body_fonts, 16)

        self.space = pymunk.Space()
        self.gi = 0
        self.g = GRAVITIES[0][1]
        self.space.gravity = (0, self.g * PPM)
        self.border = set()
        self.menu_open = True
        self.info_open = True
        self.left_wall = None
        self.info_rect = pygame.Rect(0, 0, 0, 0)
        self.build_world()

        self.tool = "block"
        self.static_mode = False
        self.paused = False
        self.physics_on = False
        self.selected = None
        self.last_body = None
        self.drag_body = None
        self.drag_local = Vec2d(0, 0)
        self.start = None
        self.contact = {}               # id(body) -> smoothed contact forces
        self.prev = {}                  # id(body) -> previous (velocity, omega) for a = dv/dt

        self.build_ui()

    # ------------------------------------------------------------------ world
    def wall_x(self):
        return LEFT + (PANEL_W if self.menu_open else 0)

    def build_world(self):
        sb = self.space.static_body
        for a, b in [((LEFT, FLOOR_Y + 4), (W, FLOOR_Y + 4)),
                     ((W - 2, -2000), (W - 2, FLOOR_Y))]:
            s = pymunk.Segment(sb, a, b, 4)
            s.friction, s.elasticity = 0.8, 0.2
            self.space.add(s)
            self.border.add(s)
        self.set_left_wall()

    def set_left_wall(self):
        """The left wall slides with the menu so objects are never hidden under it."""
        x = self.wall_x()
        if self.left_wall is not None:
            self.space.remove(self.left_wall)
            self.border.discard(self.left_wall)
        s = pymunk.Segment(self.space.static_body, (x + 2, -2000), (x + 2, FLOOR_Y), 4)
        s.friction, s.elasticity = 0.8, 0.2
        self.space.add(s)
        self.border.add(s)
        self.left_wall = s
        for b in self.space.bodies:
            if b.body_type != pymunk.Body.DYNAMIC:
                continue
            for sh in b.shapes:
                sh.cache_bb()
                if sh.bb.left < x + 8:
                    b.position = b.position + (x + 8 - sh.bb.left, 0)
                    self.space.reindex_shapes_for_body(b)

    def toggle_menu(self):
        self.menu_open = not self.menu_open
        self.set_left_wall()

    def clear(self):
        for s in list(self.space.shapes):
            if s not in self.border:
                if s.body is not self.space.static_body:
                    self.space.remove(s.body, s)
                else:
                    self.space.remove(s)
        self.selected = self.last_body = self.drag_body = None

    def build_ui(self):
        x, w, y = LEFT + 12, PANEL_W - 24, 52
        self.menu_toggle = pygame.Rect(LEFT + PANEL_W - 42, 8, 34, 34)
        self.menu_tab = pygame.Rect(LEFT + 8, 8, 44, 40)
        self.tool_buttons = {}
        for name, label in [("select", "Select / Drag"), ("line", "Line"), ("block", "Block"),
                            ("ball", "Ball"), ("erase", "Erase")]:
            self.tool_buttons[name] = Button((x, y, w, 34), label)
            y += 39
        y += 6
        self.b_static = Button((x, y, w, 34), "Static: off"); y += 39
        self.b_wplus = Button((x, y, w // 2 - 3, 34), "Weight +")
        self.b_wminus = Button((x + w // 2 + 3, y, w // 2 - 3, 34), "Weight -"); y += 39
        self.b_grav = Button((x, y, w, 34), "Gravity"); y += 39
        self.b_pause = Button((x, y, w // 2 - 3, 34), "Pause")
        self.b_clear = Button((x + w // 2 + 3, y, w // 2 - 3, 34), "Clear"); y += 39
        self.b_full = Button((x, y, w, 34), "Fullscreen (F11)"); y += 46
        self.s_density = Slider(x, y, w, 0.1, 10.0, 1.0, "Density kg/m2", "{:.1f}"); y += 52
        self.s_bounce = Slider(x, y, w, 0.0, 1.0, 0.3, "Bounciness"); y += 52
        self.s_fric = Slider(x, y, w, 0.0, 1.5, 0.7, "Friction"); y += 56
        self.b_phys = Button((x, y, w, 50), "Physics<?>")
        self.sliders = [self.s_density, self.s_bounce, self.s_fric]
        self.info_x = W - 520
        self.s_diff = Slider(self.info_x + 20, 46, 460, 1, 5, 1, "Equation difficulty", "{:.0f}", step=1)

    # --------------------------------------------------------------- creation
    def dens_px(self):
        return self.s_density.val / (PPM * PPM)

    def finish_shape(self, shape, body):
        shape.friction = self.s_fric.val
        shape.elasticity = self.s_bounce.val
        if body.body_type == pymunk.Body.DYNAMIC:
            shape.density = self.dens_px()
        self.space.add(body, shape)
        if body.body_type == pymunk.Body.DYNAMIC:
            self.last_body = self.selected = body

    def make_block(self, center, w, h):
        btype = pymunk.Body.STATIC if self.static_mode else pymunk.Body.DYNAMIC
        body = pymunk.Body(body_type=btype)
        body.position = center
        hw, hh = w / 2, h / 2
        shape = pymunk.Poly(body, [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)])
        self.finish_shape(shape, body)

    def make_ball(self, center, r):
        btype = pymunk.Body.STATIC if self.static_mode else pymunk.Body.DYNAMIC
        body = pymunk.Body(body_type=btype)
        body.position = center
        self.finish_shape(pymunk.Circle(body, r), body)

    def make_line(self, a, b):
        s = pymunk.Segment(self.space.static_body, a, b, 3)
        s.friction, s.elasticity = self.s_fric.val, self.s_bounce.val
        self.space.add(s)

    def shape_at(self, pos):
        info = self.space.point_query_nearest(pos, 3, pymunk.ShapeFilter())
        if info and info.shape not in self.border:
            return info.shape
        return None

    def change_weight(self, factor):
        b = self.selected
        if b and b in self.space.bodies and b.body_type == pymunk.Body.DYNAMIC:
            for s in b.shapes:
                s.density *= factor
                s.density = max(1e-6, s.density)

    # ---------------------------------------------------------------- physics
    def step(self):
        if not self.physics_on:
            # FROZEN: nothing moves until Physics<?> is pressed; objects can still be placed by hand
            if self.drag_body is not None:
                mouse = Vec2d(*pygame.mouse.get_pos())
                anchor = self.drag_body.local_to_world(self.drag_local)
                self.drag_body.position = self.drag_body.position + (mouse - anchor)
                self.drag_body.velocity = (0, 0)
                self.drag_body.angular_velocity = 0
                self.space.reindex_shapes_for_body(self.drag_body)
            return
        if self.drag_body is not None:
            anchor = self.drag_body.local_to_world(self.drag_local)
            mouse = Vec2d(*pygame.mouse.get_pos())
            delta = mouse - anchor
            self.drag_body.velocity = delta * 14
            self.drag_body.angular_velocity *= 0.85
        dt = 1.0 / FPS / SUB
        for _ in range(SUB):
            self.space.step(dt)
        self.measure_contacts(dt)

    def measure_contacts(self, dt):
        for body in self.space.bodies:
            if body.body_type != pymunk.Body.DYNAMIC:
                continue
            N, Fr = Vec2d(0, 0), Vec2d(0, 0)

            def cb(arb, body=body):
                nonlocal N, Fr
                pts = arb.contact_point_set.points
                if not pts:
                    return
                imp, n = arb.total_impulse, arb.normal
                if n.dot(body.position - pts[0].point_a) < 0:
                    n = -n                      # make the normal point toward this body
                j = imp.dot(n)
                s = 1 if j >= 0 else -1
                N = N + n * (abs(j) / dt / PPM)
                Fr = Fr + (imp - n * j) * (s / dt / PPM)

            body.each_arbiter(cb)
            c = self.contact.setdefault(id(body), [Vec2d(0, 0), Vec2d(0, 0)])
            c[0] = c[0] * 0.8 + N * 0.2         # smooth, otherwise the numbers flicker
            c[1] = c[1] * 0.8 + Fr * 0.2

    def forces(self, body):
        m = body.mass
        Wt = Vec2d(0, m * self.g)
        N, Fr = self.contact.get(id(body), [Vec2d(0, 0), Vec2d(0, 0)])
        if N.length < 0.02:
            N = Vec2d(0, 0)
        if Fr.length < 0.02:
            Fr = Vec2d(0, 0)
        return Wt, N, Fr, Wt + N + Fr

    # ----------------------------------------------------------------- events
    def in_info_panel(self, pos):
        return self.info_rect.collidepoint(pos)

    def mouse_down(self, pos):
        if pos[0] < LEFT:
            return
        if self.menu_open and self.menu_toggle.collidepoint(pos):
            self.toggle_menu()
            return
        if not self.menu_open and self.menu_tab.collidepoint(pos):
            self.toggle_menu()
            return
        if self.physics_on and self.info_toggle_rect().collidepoint(pos):
            self.info_open = not self.info_open
            return
        if self.menu_open and pos[0] < LEFT + PANEL_W:
            for name, b in self.tool_buttons.items():
                if b.rect.collidepoint(pos):
                    self.tool = name
            if self.b_static.rect.collidepoint(pos):
                self.static_mode = not self.static_mode
            if self.b_wplus.rect.collidepoint(pos):
                self.change_weight(1.25)
            if self.b_wminus.rect.collidepoint(pos):
                self.change_weight(0.8)
            if self.b_grav.rect.collidepoint(pos):
                self.cycle_gravity()
            if self.b_pause.rect.collidepoint(pos):
                self.paused = not self.paused
            if self.b_clear.rect.collidepoint(pos):
                self.clear()
            if self.b_full.rect.collidepoint(pos):
                pygame.display.toggle_fullscreen()
            if self.b_phys.rect.collidepoint(pos):
                self.physics_on = not self.physics_on
            for s in self.sliders:
                if s.hit(pos):
                    self.active_slider = s
                    s.set_from_mouse(pos[0])
            return
        if self.physics_on and self.info_open and self.s_diff.hit(pos):
            self.active_slider = self.s_diff
            self.s_diff.set_from_mouse(pos[0])
            return
        if self.in_info_panel(pos):
            return
        if self.tool == "select":
            sh = self.shape_at(pos)
            if sh and sh.body.body_type == pymunk.Body.DYNAMIC:
                self.drag_body = self.selected = self.last_body = sh.body
                self.drag_local = sh.body.world_to_local(Vec2d(*pos))
            else:
                self.selected = None
        elif self.tool == "erase":
            sh = self.shape_at(pos)
            if sh:
                if sh.body is self.space.static_body:
                    self.space.remove(sh)
                else:
                    if self.selected is sh.body:
                        self.selected = None
                    if self.last_body is sh.body:
                        self.last_body = None
                    self.space.remove(sh.body, sh)
        else:
            self.start = Vec2d(*pos)

    def mouse_up(self, pos):
        self.active_slider = None
        self.drag_body = None
        if self.start is None:
            return
        a, b = self.start, Vec2d(*pos)
        self.start = None
        if b.x < self.wall_x() + 8:
            b = Vec2d(self.wall_x() + 8, b.y)
        if self.tool == "line":
            if (b - a).length > 8:
                self.make_line(a, b)
        elif self.tool == "block":
            w, h = abs(b.x - a.x), abs(b.y - a.y)
            if w < 8 or h < 8:
                self.make_block(a, PPM, PPM)
            else:
                self.make_block((a + b) / 2, w, h)
        elif self.tool == "ball":
            r = (b - a).length
            self.make_ball(a, PPM / 2 if r < 6 else r)

    def cycle_gravity(self):
        self.gi = (self.gi + 1) % len(GRAVITIES)
        self.g = GRAVITIES[self.gi][1]
        self.space.gravity = (0, self.g * PPM)

    active_slider = None

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.mouse_down(e.pos)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.mouse_up(e.pos)
            elif e.type == pygame.MOUSEMOTION and self.active_slider:
                self.active_slider.set_from_mouse(e.pos[0])
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                elif e.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif e.key == pygame.K_m:
                    self.toggle_menu()
                elif e.key == pygame.K_i:
                    self.info_open = not self.info_open
                elif e.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif e.key == pygame.K_p:
                    self.physics_on = not self.physics_on
                elif e.key == pygame.K_g:
                    self.cycle_gravity()
                elif e.key == pygame.K_c:
                    self.clear()
                elif e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.change_weight(1.25)
                elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.change_weight(0.8)
                elif e.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and self.selected:
                    b = self.selected
                    if b in self.space.bodies:
                        self.space.remove(b, *b.shapes)
                    self.selected = self.last_body = None
                elif pygame.K_1 <= e.key <= pygame.K_5:
                    self.s_diff.val = e.key - pygame.K_0
        return True

    # ---------------------------------------------------------------- drawing
    @staticmethod
    def shade(dens):
        """Highlighter colours: light dense-free sky blue -> deep blue as density grows."""
        t = min(1.0, max(0.0, math.log10(max(dens, 0.1) / 0.1) / 2.0))
        return (int(190 - 110 * t), int(225 - 95 * t), int(255 - 40 * t))

    def draw_paper(self, surf):
        surf.fill(PAPER)
        for gx in range(LEFT, W, 25):
            major = ((gx - LEFT) % 50 == 0)
            pygame.draw.line(surf, GRID_MAJOR if major else GRID_MINOR, (gx, 0), (gx, H))
        y = FLOOR_Y
        while y > 0:
            major = ((FLOOR_Y - y) % 50 == 0)
            pygame.draw.line(surf, GRID_MAJOR if major else GRID_MINOR, (LEFT, y), (W, y))
            y -= 25
        # floor: a thick pen line with hatching underneath
        pygame.draw.rect(surf, (238, 230, 205), (LEFT, FLOOR_Y, W - LEFT, FLOOR_H))
        for hx in range(LEFT - FLOOR_H, W, 16):
            pygame.draw.line(surf, (190, 180, 150), (hx, FLOOR_Y + FLOOR_H), (hx + FLOOR_H, FLOOR_Y), 1)
        pygame.draw.line(surf, INK, (LEFT, FLOOR_Y), (W, FLOOR_Y), 4)
        # notebook margin + spiral binding
        pygame.draw.rect(surf, (236, 232, 218), (0, 0, LEFT, H))
        pygame.draw.line(surf, MARGIN_RED, (LEFT, 0), (LEFT, H), 3)
        for yy in range(26, H, 46):
            pygame.draw.circle(surf, (150, 145, 130), (16, yy), 8)
            pygame.draw.circle(surf, (110, 105, 95), (16, yy), 8, 2)
            pygame.draw.rect(surf, (140, 148, 165), (2, yy - 4, LEFT - 4, 8), border_radius=4)
            pygame.draw.rect(surf, (70, 78, 100), (2, yy - 4, LEFT - 4, 8), 2, border_radius=4)

    def draw_world(self, surf):
        self.draw_paper(surf)
        for sh in self.space.shapes:
            if sh in self.border:
                continue
            body = sh.body
            static = body.body_type != pymunk.Body.DYNAMIC
            col = (205, 200, 185) if static else self.shade(sh.density * PPM * PPM)
            sel = body is self.selected
            edge = (225, 40, 40) if sel else INK
            lw = 4 if sel else 3
            if isinstance(sh, pymunk.Segment):
                pygame.draw.line(surf, INK, sh.a, sh.b, int(sh.radius * 2))
                pygame.draw.circle(surf, INK, sh.a, sh.radius)
                pygame.draw.circle(surf, INK, sh.b, sh.radius)
            elif isinstance(sh, pymunk.Circle):
                c = body.local_to_world(sh.offset)
                pygame.draw.circle(surf, col, c, sh.radius)
                pygame.draw.circle(surf, edge, c, sh.radius, lw)
                tip = c + Vec2d(sh.radius, 0).rotated(body.angle)
                pygame.draw.line(surf, edge, c, tip, 2)
            else:
                pts = [body.local_to_world(v) for v in sh.get_vertices()]
                pygame.draw.polygon(surf, col, pts)
                pygame.draw.polygon(surf, edge, pts, lw)

    def text(self, surf, s, pos, color=INK, bg=True, font=None):
        t = (font or self.font).render(s, True, color)
        r = t.get_rect(topleft=pos)
        if bg:
            box = r.inflate(10, 4)
            pygame.draw.rect(surf, (255, 253, 242), box, border_radius=5)
            pygame.draw.rect(surf, color, box, 1, border_radius=5)
        surf.blit(t, r)
        return r

    def draw_physics(self, surf):
        lvl = int(self.s_diff.val)
        bodies = [b for b in self.space.bodies if b.body_type == pymunk.Body.DYNAMIC]
        for b in bodies:
            p = Vec2d(*b.position)
            Wt, N, Fr, Net = self.forces(b)
            label = (b is self.selected) or len(bodies) <= 4
            items = [(Wt, C_GRAV, "W")]
            if lvl >= 2:
                items.append((b.velocity / PPM * 3.0, C_VEL, "v"))   # velocity arrow: 3 N-units per m/s
            if lvl >= 3:
                items += [(N, C_NORM, "N"), (Fr, C_FRIC, "f"), (Net, C_NET, "ΣF")]
            if lvl >= 4:
                items.append((b.velocity / PPM * b.mass, C_MOM, "p"))
            for vec, col, name in items:
                if name == "v":
                    arrow = vec / 3.0
                    mag = arrow.length
                    pv = arrow / mag * min(150, 14 * math.sqrt(mag)) if mag > 0.05 else Vec2d(0, 0)
                    unit = "m/s"
                elif name == "p":
                    mag = vec.length
                    pv = vec / mag * min(150, 8 * math.sqrt(mag)) if mag > 0.05 else Vec2d(0, 0)
                    unit = "kg·m/s"
                else:
                    mag = vec.length
                    pv = force_to_pixels(vec)
                    unit = "N"
                if pv.length < 3:
                    continue
                draw_arrow(surf, col, p, pv, 5 if name in ("W", "ΣF") else 4)
                if label:
                    tip = p + pv
                    off = pv / pv.length * 6
                    self.text(surf, f"{name} {mag:.1f} {unit}", (tip.x + off.x - 24, tip.y + off.y - 10), col)

    def info_lines(self, b, lvl):
        g, m = self.g, b.mass
        Wt, N, Fr, Net = self.forces(b)
        v = b.velocity / PPM
        sp = v.length
        h = max(0.0, (FLOOR_Y - b.position.y) / PPM)
        KE, PE = 0.5 * m * sp * sp, m * g * h
        I = b.moment / (PPM * PPM)
        w = b.angular_velocity
        L = []
        L += [("Mass & weight", None),
              (f"m = {m:.2f} kg", WHITE),
              (f"W = m·g = {m:.2f} × {g:.2f} = {m * g:.2f} N", C_GRAV)]
        if lvl >= 2:
            L += [("Motion & energy", None),
                  (f"v = {sp:.2f} m/s   h = {h:.2f} m", C_VEL),
                  (f"KE = ½mv² = ½·{m:.2f}·{sp:.2f}² = {KE:.2f} J", C_VEL),
                  (f"PE = mgh = {m:.2f}·{g:.2f}·{h:.2f} = {PE:.2f} J", C_VEL)]
        Fx, Fy = Net.x, -Net.y
        if lvl >= 3:
            L += [("Contact forces & Newton II", None),
                  (f"N = {N.length:.2f} N   f = {Fr.length:.2f} N", C_NORM),
                  (f"ΣF = W + N + f = ({Fx:.2f}, {Fy:.2f}) N", C_NET),
                  (f"|ΣF| = {Net.length:.2f} N", C_NET),
                  (f"a = ΣF/m = {Net.length / m:.2f} m/s²", C_NET)]
        if lvl >= 4:
            L += [("Momentum & rotation", None),
                  (f"p = m·v = {m * sp:.2f} kg·m/s", C_MOM),
                  (f"I = {I:.3f} kg·m²   ω = {w:.2f} rad/s", C_MOM),
                  (f"KE_rot = ½Iω² = {0.5 * I * w * w:.3f} J", C_MOM),
                  (f"L = Iω = {I * w:.3f} kg·m²/s", C_MOM)]
        if lvl >= 5:
            ang = math.degrees(math.atan2(Fy, Fx)) if Net.length > 0.01 else 0.0
            power = Net.x * v.x + Net.y * v.y
            mu = Fr.length / N.length if N.length > 0.05 else 0.0
            L += [("Full analysis", None),
                  (f"E = KE+KE_rot+PE = {KE + 0.5 * I * w * w + PE:.2f} J", WHITE),
                  (f"P = ΣF·v = {power:.2f} W", WHITE),
                  (f"θ(ΣF) = atan2(ΣFy, ΣFx) = {ang:.1f}°", WHITE),
                  (f"μ_eff = f/N = {mu:.2f}   N/W = {N.length / max(m * g, 1e-9):.2f}", WHITE),
                  (f"Impulse/frame J = ΣF·Δt = {Net.length / FPS:.3f} N·s", WHITE)]
            total = 0.0
            for bb in self.space.bodies:
                if bb.body_type == pymunk.Body.DYNAMIC:
                    vv = (bb.velocity / PPM).length
                    ii = bb.moment / (PPM * PPM)
                    hh = max(0.0, (FLOOR_Y - bb.position.y) / PPM)
                    total += 0.5 * bb.mass * vv * vv + 0.5 * ii * bb.angular_velocity ** 2 + bb.mass * g * hh
            L += [(f"Whole scene energy = {total:.2f} J", (10, 120, 70))]
        return L

    def info_toggle_rect(self):
        if self.info_open:
            return pygame.Rect(self.info_x + 500 - 44, 12, 34, 34)
        return pygame.Rect(W - 230, 8, 220, 40)

    def draw_info_panel(self, surf):
        lvl = int(self.s_diff.val)
        if not self.info_open:
            r = self.info_toggle_rect()
            self.info_rect = r
            pygame.draw.rect(surf, (200, 190, 160), r.move(2, 2), border_radius=8)
            pygame.draw.rect(surf, CARD, r, border_radius=8)
            pygame.draw.rect(surf, INK, r, 2, border_radius=8)
            surf.blit(self.big.render("Equations", True, INK), (r.x + 14, r.y + 8))
            draw_chevron(surf, pygame.Rect(r.right - 40, r.y + 3, 34, 34), "down")
            return
        b = self.selected if self.selected in self.space.bodies else self.last_body
        lines = self.info_lines(b, lvl) if (b is not None and b in self.space.bodies) else []
        row = 24
        h = 120 + row * max(len(lines), 2) + 46
        r = pygame.Rect(self.info_x, 6, 500, h)
        self.info_rect = r
        pygame.draw.rect(surf, (200, 190, 160), r.move(3, 3), border_radius=10)
        pygame.draw.rect(surf, CARD, r, border_radius=10)
        pygame.draw.rect(surf, INK, r, 2, border_radius=10)
        self.text(surf, f"Physics notes - level {lvl}: {LEVELS[lvl - 1]}", (r.x + 16, r.y + 10), INK, bg=False, font=self.hand)
        draw_chevron(surf, self.info_toggle_rect(), "up")
        self.s_diff.y = 46
        self.s_diff.rect.y = 46 + 26
        self.s_diff.draw(surf, self.font)
        self.text(surf, f"gravity g = {self.g:.2f} m/s²", (r.x + 20, r.y + 86), INK_SOFT, bg=False)
        y = r.y + 118
        if not lines:
            self.text(surf, "Drop a block or ball to see its equations.", (r.x + 20, y), INK, bg=False)
        for s, col in lines:
            if col is None:
                self.text(surf, s.upper(), (r.x + 18, y + 2), INK_SOFT, bg=False, font=self.font)
                pygame.draw.line(surf, (200, 190, 160), (r.x + 16, y + row - 2), (r.right - 16, y + row - 2), 1)
            else:
                self.text(surf, s, (r.x + 28, y), col, bg=False)
            y += row
        # legend row
        lx = r.x + 18
        ly = r.bottom - 30
        for name, col in [("Weight", C_GRAV), ("Velocity", C_VEL), ("Normal", C_NORM),
                          ("Friction", C_FRIC), ("Net", C_NET), ("Momentum", C_MOM)]:
            pygame.draw.rect(surf, col, (lx, ly + 5, 12, 12), border_radius=2)
            t = self.text(surf, name, (lx + 16, ly), col, bg=False, font=self.small)
            lx = t.right + 12

    def draw_ui(self, surf):
        if not self.menu_open:
            r = self.menu_tab
            pygame.draw.rect(surf, (200, 190, 160), r.move(2, 2), border_radius=8)
            pygame.draw.rect(surf, HILITE if r.collidepoint(pygame.mouse.get_pos()) else CARD, r, border_radius=8)
            pygame.draw.rect(surf, INK, r, 2, border_radius=8)
            draw_hamburger(surf, r)
            return
        panel = pygame.Rect(LEFT, 0, PANEL_W, H)
        pygame.draw.rect(surf, CARD, panel)
        pygame.draw.line(surf, INK, (panel.right, 0), (panel.right, H), 3)
        self.text(surf, "Notebook", (LEFT + 14, 8), INK, bg=False, font=self.hand)
        pygame.draw.rect(surf, (253, 250, 238), self.menu_toggle, border_radius=7)
        pygame.draw.rect(surf, INK, self.menu_toggle, 2, border_radius=7)
        draw_chevron(surf, self.menu_toggle, "left")
        for name, b in self.tool_buttons.items():
            b.draw(surf, self.font, active=(self.tool == name))
        self.b_static.draw(surf, self.font, self.static_mode, f"Static: {'ON' if self.static_mode else 'off'}")
        self.b_wplus.draw(surf, self.font)
        self.b_wminus.draw(surf, self.font)
        self.b_grav.draw(surf, self.font, label=f"G: {GRAVITIES[self.gi][0]} {self.g:.2f}")
        self.b_pause.draw(surf, self.font, self.paused, "Resume" if self.paused else "Pause")
        self.b_clear.draw(surf, self.font)
        self.b_full.draw(surf, self.font)
        for s in self.sliders:
            s.draw(surf, self.font)
        self.b_phys.draw(surf, self.big, self.physics_on, active_col=(170, 240, 170))
        if not self.physics_on:
            self.text(surf, "frozen until pressed", (self.b_phys.rect.x + 4, self.b_phys.rect.bottom + 8),
                      C_NET, bg=False)
        hint = {"select": "drag objects", "line": "drag a line", "block": "click or drag a block",
                "ball": "click or drag a ball", "erase": "click to delete"}[self.tool]
        self.text(surf, hint, (LEFT + 14, H - 30), INK_SOFT, bg=False)
        if self.selected in self.space.bodies:
            self.text(surf, f"selected: {self.selected.mass:.2f} kg", (LEFT + 14, H - 56), C_GRAV, bg=False)

    def draw_preview(self, surf):
        if self.start is None:
            return
        a, b = self.start, Vec2d(*pygame.mouse.get_pos())
        col = INK
        if self.tool == "line":
            pygame.draw.line(surf, col, a, b, 3)
        elif self.tool == "block":
            pygame.draw.rect(surf, col, pygame.Rect(min(a.x, b.x), min(a.y, b.y), abs(b.x - a.x), abs(b.y - a.y)), 2)
            self.text(surf, f"{abs(b.x - a.x) / PPM:.1f} × {abs(b.y - a.y) / PPM:.1f} m", (b.x + 12, b.y + 12))
        elif self.tool == "ball":
            r = (b - a).length
            pygame.draw.circle(surf, col, a, r, 2)
            self.text(surf, f"r = {r / PPM:.2f} m", (b.x + 10, b.y + 10))

    def draw(self):
        s = self.screen
        self.draw_world(s)
        if self.physics_on:
            self.draw_physics(s)
        self.draw_preview(s)
        if not self.physics_on:
            self.text(s, "Frozen - set up your drawing, then press Physics<?> (P)", (self.wall_x() + 66, 12), C_VEL, bg=True, font=self.big)
        draw_shrimp(s, W - 55, H - 52, 0.9)          # the shrimp, bottom-right
        if self.physics_on:
            self.draw_info_panel(s)
        else:
            self.info_rect = pygame.Rect(0, 0, 0, 0)
        self.draw_ui(s)
        pygame.display.flip()

    # ------------------------------------------------------------------- loop
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            if not self.paused:
                self.step()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    Game().run()