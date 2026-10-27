"""
尋問室ビンタゲーム (pygame)  ※ interrogation_ragdoll.py と同じフォルダに置いてください
  pip install pygame

ルール:
  ・制限時間30秒。首の据わっていない男の頭にビンタを当てると +30pt
  ・手はマウスに遅れて(しかもラグが揺れ動く)ついてくる
  ・クリックでビンタ。振り抜いた瞬間の「手の位置」で判定される
  ・薄い輪っか = 本当のマウス位置 / 手 = ラグった実際の位置

操作: クリック=ビンタ  SPACE/ENTER=開始・リトライ  ESC=終了
"""
import math
import random
import sys
from collections import deque

import pygame

import interrogation_ragdoll as base
from interrogation_ragdoll import Ragdoll, draw_scene, W, H, FPS, SKIN, SKIN_SHADE

GAME_TIME = 30.0
HIT_POINTS = 30
SWING_TIME = 0.22
IMPACT_AT = 0.10
HIT_RADIUS = 78          # 頭中心との当たり半径(手の大きさ込み)


class Floater:
    def __init__(self, text, x, y, color):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.y -= 70 * dt
        return self.t < 0.9


class Spark:
    def __init__(self, x, y):
        a = random.uniform(0, math.tau)
        s = random.uniform(160, 460)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.t = 0.0
        self.life = random.uniform(0.25, 0.5)

    def update(self, dt):
        self.t += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 600 * dt
        return self.t < self.life


def draw_hand(surf, pos, angle_deg, scale):
    """開いた手のひら。angle_degで振りの傾き。"""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)

    def P(x, y):
        x, y = x * scale, y * scale
        return (pos[0] + x * ca - y * sa, pos[1] + x * sa + y * ca)

    # 袖口
    pygame.draw.polygon(surf, (240, 240, 236), [P(-24, 34), P(24, 34), P(28, 80), P(-28, 80)])
    # 指(4本)
    for i, (fx, fl) in enumerate(((-19, 40), (-6, 48), (7, 46), (20, 38))):
        pygame.draw.polygon(surf, SKIN, [P(fx - 6, 0), P(fx + 6, 0), P(fx + 5, -fl), P(fx - 5, -fl)])
        pygame.draw.polygon(surf, SKIN_SHADE, [P(fx - 6, 0), P(fx + 6, 0), P(fx + 5, -fl), P(fx - 5, -fl)], 2)
    # 手のひら
    pygame.draw.polygon(surf, SKIN, [P(-26, 0), P(26, 0), P(26, 34), P(-26, 34)])
    pygame.draw.polygon(surf, SKIN_SHADE, [P(-26, 0), P(26, 0), P(26, 34), P(-26, 34)], 2)
    # 親指
    pygame.draw.polygon(surf, SKIN, [P(-26, 8), P(-44, 4), P(-42, 20), P(-26, 28)])
    pygame.draw.polygon(surf, SKIN_SHADE, [P(-26, 8), P(-44, 4), P(-42, 20), P(-26, 28)], 2)


def rank_text(score):
    if score == 0:
        return "空振り職人"
    if score <= 30:
        return "まぐれ当たり"
    if score <= 90:
        return "尋問官見習い"
    if score <= 180:
        return "手練れ"
    return "神の手"


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("尋問室ビンタ")
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)

    def font(sz):
        return pygame.font.SysFont("meiryo,msgothic,notosanscjkjp,sans", sz, bold=True)

    f_s, f_m, f_l, f_xl = font(20), font(30), font(54), font(96)
    canvas = pygame.Surface((W, H))

    anchor = (W // 2, 330)
    doll = Ragdoll(anchor)

    state = "title"          # title / play / result
    best = 0
    score = 0
    time_left = GAME_TIME
    sway = sway_v = 0.0
    tick = 0
    clock_t = 0.0
    history = deque()        # (時刻, x, y)
    hand = [W / 2, H / 2]
    hand_prev = hand[:]
    swing = None             # スイング経過時間 or None
    impact_done = False
    shake = 0.0
    flash = 0.0
    floaters, sparks = [], []
    next_jolt = 1.0
    hits = swings = 0

    def reset():
        nonlocal score, time_left, sway, sway_v, swing, impact_done, shake, flash
        nonlocal floaters, sparks, next_jolt, hits, swings
        doll.reset()
        score, time_left = 0, GAME_TIME
        sway = sway_v = 0.0
        swing, impact_done, shake, flash = None, False, 0.0, 0.0
        floaters, sparks = [], []
        next_jolt = 0.8
        hits = swings = 0

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 1 / 30)
        tick += 1
        clock_t += dt
        mx, my = pygame.mouse.get_pos()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if e.key in (pygame.K_SPACE, pygame.K_RETURN) and state in ("title", "result"):
                    reset(); state = "play"
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if state == "play" and swing is None:
                    swing, impact_done = 0.0, False
                    swings += 1
                elif state in ("title", "result") and tick > 30:
                    reset(); state = "play"

        # ---- 手のラグ(遅延 + 揺れるラグ量 + 追従のなまり) ----
        history.append((clock_t, mx, my))
        lag = 0.13 + 0.12 * (0.5 + 0.5 * math.sin(clock_t * 1.7)) + 0.04 * math.sin(clock_t * 5.3)
        while len(history) > 2 and history[1][0] < clock_t - 0.6:
            history.popleft()
        target = history[0][1:]
        for h in history:
            if h[0] <= clock_t - lag:
                target = h[1:]
            else:
                break
        hand_prev = hand[:]
        k = min(1.0, dt * 14)
        hand[0] += (target[0] - hand[0]) * k
        hand[1] += (target[1] - hand[1]) * k
        hvx = (hand[0] - hand_prev[0]) / dt if dt else 0.0
        hvy = (hand[1] - hand_prev[1]) / dt if dt else 0.0

        # ---- ゲーム進行 ----
        if state == "play":
            time_left -= dt
            if time_left <= 0:
                time_left = 0
                state = "result"
                best = max(best, score)
                swing = None

            # 男がランダムにガクッと揺れる
            next_jolt -= dt
            if next_jolt <= 0:
                next_jolt = random.uniform(0.6, 1.5)
                sway_v += random.choice((-1, 1)) * random.uniform(80, 220)
                doll.impulse(random.uniform(-7, 7), random.uniform(-10, -2))

            if swing is not None:
                swing += dt
                if not impact_done and swing >= IMPACT_AT:
                    impact_done = True
                    c, t = doll.chin, doll.top
                    cx, cy = (c.x + t.x) / 2, (c.y + t.y) / 2
                    if math.hypot(hand[0] - cx, hand[1] - cy) <= HIT_RADIUS:
                        score += HIT_POINTS
                        hits += 1
                        shake, flash = 14.0, 0.18
                        doll.impulse(14 + max(0.0, hvx) * 0.012, -4 + hvy * 0.008)
                        sway_v += 420
                        floaters.append(Floater("+%d" % HIT_POINTS, cx, cy - 60, (255, 230, 90)))
                        floaters.append(Floater("パァン!", cx + 40, cy - 10, (255, 120, 90)))
                        sparks += [Spark(cx, cy) for _ in range(22)]
                    else:
                        floaters.append(Floater("空振り", hand[0], hand[1] - 40, (200, 200, 210)))
                if swing >= SWING_TIME:
                    swing = None

        # ---- 物理 ----
        sway_v += (-sway * 40.0) * dt
        sway_v *= 0.93
        sway += sway_v * dt
        breath = math.sin(tick * 0.04) * 1.5
        doll.step(dt, (anchor[0] + sway, anchor[1] + breath), None)

        floaters = [f for f in floaters if f.update(dt)]
        sparks = [s for s in sparks if s.update(dt)]
        shake = max(0.0, shake - 40 * dt)
        flash = max(0.0, flash - dt)

        # ---- 描画 ----
        draw_scene(canvas, doll, sway, tick)

        for s in sparks:
            pygame.draw.circle(canvas, (255, 220, 120), (int(s.x), int(s.y)), 4)
        for f in floaters:
            img = f_l.render(f.text, True, f.color)
            img.set_alpha(max(0, int(255 * (1 - f.t / 0.9))))
            canvas.blit(img, img.get_rect(center=(int(f.x), int(f.y))))

        # 本当のマウス位置(薄い輪)
        if state == "play":
            pygame.draw.circle(canvas, (255, 255, 255), (mx, my), 18, 2)
            pygame.draw.circle(canvas, (255, 255, 255), (mx, my), 2)
            # 手
            if swing is not None:
                p = swing / SWING_TIME
                ang = -55 + 110 * (p * p * (3 - 2 * p))
                sc = 1.0 + 0.3 * math.sin(p * math.pi)
            else:
                ang, sc = -20, 1.0
            draw_hand(canvas, (hand[0], hand[1]), ang, sc)

        # HUD
        if state in ("play", "result"):
            pygame.draw.rect(canvas, (20, 20, 24), (0, 0, W, 54))
            canvas.blit(f_m.render("SCORE %d" % score, True, (255, 230, 90)), (18, 8))
            bar_w = 300
            pygame.draw.rect(canvas, (70, 70, 76), (W // 2 - bar_w // 2, 18, bar_w, 20), border_radius=6)
            ratio = time_left / GAME_TIME
            col = (110, 220, 130) if ratio > 0.34 else (235, 90, 80)
            pygame.draw.rect(canvas, col, (W // 2 - bar_w // 2, 18, int(bar_w * ratio), 20), border_radius=6)
            tl = f_m.render("%04.1f" % time_left, True, (240, 240, 240))
            canvas.blit(tl, (W - tl.get_width() - 18, 8))

        if flash > 0:
            fl = pygame.Surface((W, H))
            fl.fill((255, 255, 255))
            fl.set_alpha(int(180 * flash / 0.18))
            canvas.blit(fl, (0, 0))

        if state == "title":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            canvas.blit(ov, (0, 0))
            lines = [
                (f_xl, "尋問室ビンタ", (255, 240, 200), 150),
                (f_m, "首の据わらない男の頭を、ラグった手でひっぱたけ", (230, 230, 230), 250),
                (f_s, "クリック=ビンタ   命中 +30pt   制限時間 30秒", (210, 210, 210), 320),
                (f_s, "薄い輪っか=あなたのマウス / 手はそれより遅れてついてくる", (210, 210, 210), 352),
                (f_m, "クリック or SPACE でスタート", (255, 230, 90), 440),
            ]
            for fnt, txt, colr, y in lines:
                img = fnt.render(txt, True, colr)
                canvas.blit(img, img.get_rect(center=(W // 2, y)))
            canvas.blit(f_s.render("", True, (0, 0, 0)), (0, 0))
            pygame.mouse.set_visible(True)
        elif state == "result":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 170))
            canvas.blit(ov, (0, 0))
            acc = (100 * hits // swings) if swings else 0
            lines = [
                (f_l, "TIME UP", (255, 240, 200), 140),
                (f_xl, "%d pt" % score, (255, 230, 90), 240),
                (f_m, "称号: " + rank_text(score), (240, 240, 240), 330),
                (f_s, "命中 %d / %d 回 (%d%%)    ベスト %d pt" % (hits, swings, acc, best), (210, 210, 210), 380),
                (f_m, "クリック or SPACE でリトライ", (255, 230, 90), 460),
            ]
            for fnt, txt, colr, y in lines:
                img = fnt.render(txt, True, colr)
                canvas.blit(img, img.get_rect(center=(W // 2, y)))
            pygame.mouse.set_visible(True)
        else:
            pygame.mouse.set_visible(False)

        ox = random.uniform(-shake, shake) if shake else 0
        oy = random.uniform(-shake, shake) if shake else 0
        screen.fill((0, 0, 0))
        screen.blit(canvas, (ox, oy))
        pygame.display.flip()


if __name__ == "__main__":
    main()
