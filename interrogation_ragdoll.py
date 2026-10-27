"""
尋問室ラグドール・プロトタイプ (pygame)
  pip install pygame

操作:
  マウスドラッグ : 頭をつかんで振り回す
  SPACE          : 机をドン!と叩く(上半身ごとガクッと揺れる)
  ←/→            : 椅子ごと左右に揺らす
  R              : リセット
  ESC            : 終了

首が完全に据わっておらず、頭が胴体の一点だけで吊られている
Verlet積分のラグドールです。
"""
import math
import random
import sys

import pygame

W, H = 960, 640
FPS = 60
SUBSTEPS = 8
ITER = 6
GRAVITY = 1400.0
DAMPING = 0.995

# ---- 色 ----
WALL = (74, 78, 82)
WALL_DARK = (54, 58, 62)
FLOOR = (38, 38, 42)
DESK = (96, 70, 48)
DESK_EDGE = (66, 46, 30)
CHAIR = (28, 28, 32)
SKIN = (222, 184, 152)
SKIN_SHADE = (176, 134, 108)
HAIR = (24, 20, 20)
SHIRT = (240, 240, 236)
SHIRT_SHADE = (205, 205, 200)
VEST = (26, 26, 30)
EYE_SHADOW = (92, 60, 50)


class Vec:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y


class Point:
    def __init__(self, x, y, pinned=False):
        self.p = Vec(x, y)
        self.o = Vec(x, y)
        self.pinned = pinned


class Ragdoll:
    """首チェーン + 剛体の頭(2点)。頭は根元の1点でぶら下がるだけ。"""

    NECK_SEG = 11
    NECK_N = 3
    HEAD_LEN = 100

    def __init__(self, anchor):
        self.anchor = anchor
        self.reset()

    def reset(self):
        ax, ay = self.anchor
        self.pts = [Point(ax, ay, pinned=True)]
        for i in range(1, self.NECK_N + 1):
            self.pts.append(Point(ax, ay - i * self.NECK_SEG))
        cx, cy = self.pts[-1].p.x, self.pts[-1].p.y
        # 最初から少し傾けて、ガクッと垂れる感じに
        self.pts.append(Point(cx + 30, cy - self.HEAD_LEN + 10))
        self.links = []
        for i in range(self.NECK_N):
            self.links.append((i, i + 1, self.NECK_SEG))
        self.links.append((self.NECK_N, self.NECK_N + 1, self.HEAD_LEN))
        self.grab = None

    @property
    def chin(self):
        return self.pts[self.NECK_N].p

    @property
    def top(self):
        return self.pts[self.NECK_N + 1].p

    def impulse(self, ix, iy):
        for pt in self.pts[1:]:
            pt.o.x -= ix
            pt.o.y -= iy

    def step(self, dt, anchor_pos, mouse):
        self.pts[0].p.x, self.pts[0].p.y = anchor_pos
        self.pts[0].o.x, self.pts[0].o.y = anchor_pos
        if self.grab is not None and mouse is not None:
            g = self.pts[self.grab]
            g.p.x, g.p.y = mouse
            g.o.x, g.o.y = mouse
        h = dt / SUBSTEPS
        for _ in range(SUBSTEPS):
            for i, pt in enumerate(self.pts):
                if pt.pinned or i == self.grab:
                    continue
                vx = (pt.p.x - pt.o.x) * DAMPING
                vy = (pt.p.y - pt.o.y) * DAMPING
                pt.o.x, pt.o.y = pt.p.x, pt.p.y
                pt.p.x += vx
                pt.p.y += vy + GRAVITY * h * h
            for _ in range(ITER):
                for a, b, length in self.links:
                    pa, pb = self.pts[a], self.pts[b]
                    dx, dy = pb.p.x - pa.p.x, pb.p.y - pa.p.y
                    d = math.hypot(dx, dy) or 1e-6
                    diff = (d - length) / d
                    wa = 0.0 if (pa.pinned or a == self.grab) else 1.0
                    wb = 0.0 if (pb.pinned or b == self.grab) else 1.0
                    wsum = wa + wb
                    if wsum == 0:
                        continue
                    pa.p.x += dx * diff * wa / wsum
                    pa.p.y += dy * diff * wa / wsum
                    pb.p.x -= dx * diff * wb / wsum
                    pb.p.y -= dy * diff * wb / wsum
                # 机との当たり
                for pt in self.pts[1:]:
                    if pt.p.y > DESK_Y - 4:
                        pt.p.y = DESK_Y - 4
                        pt.o.x = pt.p.x - (pt.p.x - pt.o.x) * 0.6
                    pt.p.x = max(20, min(W - 20, pt.p.x))


DESK_Y = 470


def lt(c, u, r, x, y):
    """頭のローカル座標(x:右, y:顎→頭頂)をスクリーン座標へ"""
    return (c.x + r[0] * x + u[0] * y, c.y + r[1] * x + u[1] * y)


def draw_head(surf, doll, tick):
    c, t = doll.chin, doll.top
    ux, uy = t.x - c.x, t.y - c.y
    n = math.hypot(ux, uy) or 1.0
    u = (ux / n, uy / n)
    r = (-u[1], u[0])
    L = lambda x, y: lt(c, u, r, x, y)

    # 首
    neck = [(p.p.x, p.p.y) for p in doll.pts[: doll.NECK_N + 1]]
    pygame.draw.lines(surf, SKIN_SHADE, False, neck, 22)
    for p in neck:
        pygame.draw.circle(surf, SKIN_SHADE, (int(p[0]), int(p[1])), 11)

    # 頭(彫りの深い角ばった輪郭)
    outline = [
        L(-14, 0), L(14, 0),
        L(30, 18), L(40, 44), L(41, 70), L(32, 92),
        L(0, 104), L(-32, 92), L(-41, 70), L(-40, 44), L(-30, 18),
    ]
    pygame.draw.polygon(surf, SKIN, outline)
    pygame.draw.polygon(surf, SKIN_SHADE, outline, 3)

    # 髪
    hair = [L(-41, 70), L(-36, 98), L(0, 112), L(36, 98), L(41, 70),
            L(32, 82), L(10, 90), L(-12, 86), L(-30, 80)]
    pygame.draw.polygon(surf, HAIR, hair)

    # 頬の陰影(彫りの深さ)
    pygame.draw.polygon(surf, SKIN_SHADE, [L(-38, 40), L(-26, 30), L(-24, 14), L(-32, 20)])
    pygame.draw.polygon(surf, SKIN_SHADE, [L(38, 40), L(26, 30), L(24, 14), L(32, 20)])

    # 眉骨 + 落ち窪んだ目
    for s in (-1, 1):
        pygame.draw.polygon(surf, HAIR, [L(s * 6, 70), L(s * 36, 72), L(s * 34, 77), L(s * 6, 75)])
        cx_, cy_ = L(s * 20, 62)
        pygame.draw.ellipse(surf, EYE_SHADOW, pygame.Rect(cx_ - 14, cy_ - 8, 28, 16))
        # 白目が「ぐらぐら」するのは頭の傾きに合わせて瞳を少し流す
        ex, ey = L(s * 20 + 2 * math.sin(tick * 0.05), 62)
        pygame.draw.circle(surf, (245, 245, 245), (int(ex), int(ey)), 6)
        pygame.draw.circle(surf, (20, 16, 16), (int(ex + u[0] * -1), int(ey + 1)), 3)

    # 鼻(高い鼻筋)
    pygame.draw.polygon(surf, SKIN_SHADE, [L(-2, 66), L(2, 66), L(9, 34), L(-9, 34)])
    pygame.draw.line(surf, SKIN_SHADE, L(-9, 34), L(9, 34), 3)

    # 口(へ)
    pygame.draw.lines(surf, (110, 60, 56), False, [L(-12, 20), L(0, 17), L(12, 20)], 3)


def draw_scene(surf, doll, sway, tick):
    surf.fill(WALL)
    pygame.draw.rect(surf, WALL_DARK, (0, 0, W, 90))
    pygame.draw.rect(surf, FLOOR, (0, DESK_Y + 60, W, H))
    # マジックミラー風の窓
    pygame.draw.rect(surf, (30, 38, 44), (70, 120, 220, 150))
    pygame.draw.rect(surf, (110, 120, 126), (70, 120, 220, 150), 6)
    pygame.draw.polygon(surf, (50, 62, 70), [(80, 130), (160, 130), (120, 260), (80, 260)])
    # 天井ランプ + 光
    pygame.draw.line(surf, (20, 20, 20), (W // 2, 0), (W // 2, 70), 3)
    pygame.draw.polygon(surf, (30, 30, 30), [(W // 2 - 50, 100), (W // 2 + 50, 100), (W // 2 + 20, 70), (W // 2 - 20, 70)])
    light = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.polygon(light, (255, 240, 180, 38),
                        [(W // 2 - 40, 100), (W // 2 + 40, 100), (W // 2 + 260, DESK_Y), (W // 2 - 260, DESK_Y)])
    surf.blit(light, (0, 0))

    ax, ay = doll.anchor
    bx = int(sway)

    # 椅子の背もたれ
    pygame.draw.rect(surf, CHAIR, (ax - 120 + bx, ay - 40, 240, 260), border_radius=22)
    pygame.draw.rect(surf, (48, 48, 54), (ax - 120 + bx, ay - 40, 240, 260), 4, border_radius=22)

    # 胴体(シャツ + 黒チョッキ)
    shoulder_l = (ax - 90 + bx, ay + 10)
    shoulder_r = (ax + 90 + bx, ay + 10)
    waist_l = (ax - 70 + bx, DESK_Y + 10)
    waist_r = (ax + 70 + bx, DESK_Y + 10)
    pygame.draw.polygon(surf, SHIRT, [shoulder_l, (ax - 14 + bx, ay - 4), (ax + 14 + bx, ay - 4), shoulder_r, waist_r, waist_l])
    # 袖(腕)→ 机の上の手
    for s in (-1, 1):
        sh = (ax + s * 90 + bx, ay + 14)
        el = (ax + s * 118 + bx, ay + 130)
        hd = (ax + s * 70 + bx, DESK_Y - 8)
        pygame.draw.line(surf, SHIRT, sh, el, 34)
        pygame.draw.line(surf, SHIRT_SHADE, el, hd, 30)
        pygame.draw.circle(surf, SKIN, hd, 15)
    # チョッキ
    vest_l = [(ax - 80 + bx, ay + 16), (ax - 16 + bx, ay + 4), (ax + bx, ay + 90),
              (ax + 16 + bx, ay + 4), (ax + 80 + bx, ay + 16), (ax + 66 + bx, DESK_Y + 10), (ax - 66 + bx, DESK_Y + 10)]
    pygame.draw.polygon(surf, VEST, vest_l)
    for i in range(5):
        pygame.draw.circle(surf, (80, 80, 86), (ax + bx, ay + 120 + i * 50), 4)

    # 頭(首は肩のアンカーに追従)
    draw_head(surf, doll, tick)

    # 机
    pygame.draw.rect(surf, DESK, (0, DESK_Y, W, 40))
    pygame.draw.rect(surf, DESK_EDGE, (0, DESK_Y + 40, W, 100))
    pygame.draw.line(surf, (140, 108, 80), (0, DESK_Y), (W, DESK_Y), 3)
    # 机上の小物(書類とスタンド)
    pygame.draw.rect(surf, (230, 230, 220), (W // 2 - 160, DESK_Y + 6, 90, 22))
    pygame.draw.rect(surf, (60, 60, 60), (W // 2 + 120, DESK_Y - 14, 30, 22))


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("尋問室 ラグドール")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("meiryo,msgothic,notosanscjkjp,sans", 18)

    anchor = (W // 2, 330)
    doll = Ragdoll(anchor)
    sway = 0.0
    sway_v = 0.0
    tick = 0
    shake_timer = 0.0

    while True:
        dt = clock.tick(FPS) / 1000.0
        tick += 1
        mouse = pygame.mouse.get_pos()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if e.key == pygame.K_r:
                    doll.reset(); sway = sway_v = 0.0
                if e.key == pygame.K_SPACE:
                    # 机ドン: 体が跳ね、頭は慣性で置いていかれる
                    sway_v += random.choice((-1, 1)) * 260
                    doll.impulse(random.uniform(-6, 6), -14)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                best, bd = None, 1e9
                for i in range(doll.NECK_N, len(doll.pts)):
                    d = math.hypot(doll.pts[i].p.x - mouse[0], doll.pts[i].p.y - mouse[1])
                    if d < bd:
                        best, bd = i, d
                if bd < 90:
                    doll.grab = best
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                doll.grab = None

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            sway_v -= 900 * dt
        if keys[pygame.K_RIGHT]:
            sway_v += 900 * dt

        # 胴体の横揺れ(バネ)
        sway_v += (-sway * 40.0) * dt
        sway_v *= 0.93
        sway += sway_v * dt
        # ゆるい呼吸
        breath = math.sin(tick * 0.04) * 1.5
        anchor_pos = (anchor[0] + sway, anchor[1] + breath)

        doll.step(dt, anchor_pos, mouse if doll.grab is not None else None)

        draw_scene(screen, doll, sway, tick)
        screen.blit(font.render("ドラッグ:頭  SPACE:机ドン  ←→:椅子揺らし  R:リセット", True, (230, 230, 230)), (14, 12))
        pygame.display.flip()


if __name__ == "__main__":
    main()
