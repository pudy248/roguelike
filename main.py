import numpy
import os
import sys
import time
from math import hypot
from multiprocessing.pool import Pool
from threading import Thread

import pygame as pg

from noise import Noise


class Tile:
    def __init__(self, pos):
        self.pos = pos
        self.id = 0


class Chunk:
    def __init__(self, pos):
        self.pos = pos
        self.loaded = False
        self.tiledict = {}
        for y in range(CHUNKSIZE):
            for x in range(CHUNKSIZE):
                t = Tile((self.pos[0] * CHUNKSIZE + x, self.pos[1] * CHUNKSIZE + y))
                self.tiledict.update({(x, y): t})

    def generate(self, chunksize, N):
        for x in range(chunksize):
            for y in range(chunksize):
                s = self.tiledict[x, y]
                s.id = 1 if N.interp_avg(x + N.AVG_RADIUS + (self.pos[0] * chunksize), y + N.AVG_RADIUS + (self.pos[1] * chunksize)) > N.AVG_CUTOFF else 0
        self.loaded = True
        return self

    def draw(self):
        if self.loaded:
            if self.pos not in world.surfaces.keys():
                tile_dark = pg.transform.scale(sprites["tile_dark"], (1, 1))
                tile_light = pg.transform.scale(sprites["tile_light"], (1, 1))
                tile_green = pg.transform.scale(sprites["tile_green"], (1, 1))
                surface = pg.Surface((CHUNKSIZE, CHUNKSIZE))
                for k in self.tiledict.keys():
                    tile = self.tiledict[k]
                    a = world.get_tile_id(tile.pos[0] - 1, tile.pos[1]) == 1 or world.get_tile_id(tile.pos[0] + 1, tile.pos[1]) == 1 or world.get_tile_id(tile.pos[0], tile.pos[1] + 1) == 1 or world.get_tile_id(tile.pos[0], tile.pos[1] - 1) == 1
                    surface.blit((tile_green if a else tile_dark) if tile.id == 0 else tile_light, (k[0], k[1]))
                surface = pg.transform.scale(surface, (CHUNKSIZE * SCALING, CHUNKSIZE * SCALING))
                world.surfaces.update({self.pos: surface})
            SURF.blit(world.surfaces[self.pos], ((self.pos[0] * CHUNKSIZE - player.world_pos[0]) * SCALING + int(W / 2), (self.pos[1] * CHUNKSIZE - player.world_pos[1]) * SCALING + int(H / 2)))


class World:
    def __init__(self):
        self.pool = Pool()
        self.chunks = {}
        self.surfaces = {}
        self.threads = {}
        self.global_tiledict = {}
        self.percent_loaded = 0
        for x in range(-CHUNKLOAD_RADIUS, CHUNKLOAD_RADIUS + 1):
            for y in range(-CHUNKLOAD_RADIUS, CHUNKLOAD_RADIUS + 1):
                self.chunks.update({(x, y): Chunk((x, y))})

    def loading_check(self):
        a = True
        b = 0
        for c in self.chunks.values():
            if not c.loaded:
                a = False
            else:
                b += 1
        self.percent_loaded = b / len(self.chunks.keys())
        return a

    def load_all(self):
        for k in self.chunks:
            self.load_chunk(k)

    def load_chunk(self, coords):
        if coords not in self.threads.keys():
            self.chunks.update({coords: Chunk(coords)})
            self.threads.update({coords: self.pool.apply_async(self.chunks[coords].generate, (CHUNKSIZE, N))})
            thr = Thread(target=self.post_chunk_load, args=(coords, ))
            thr.start()

    def post_chunk_load(self, coords):
        r = self.threads[coords].get()
        self.chunks[coords] = r
        self.threads.pop(coords)
        for t in self.chunks[coords].tiledict.values():
            self.global_tiledict.update({(t.pos[0], t.pos[1]): t})
        numpy.random.seed(coords[0] * coords[1] + N.SEED)
        for i in range(int(ENEMIES_PER_CHUNK * numpy.power(1.05, min(30, coords[1])))):
            enemyGroup.add(Enemy([(coords[0] + numpy.random.random()) * CHUNKSIZE,
                (coords[1] + numpy.random.random()) * CHUNKSIZE], [0, 0], -1, sprites["tile_blue"], 1, 10000, enemy_choose(coords[1] * 2).__copy__()))
        self.loading_check()
        print(str(int(self.percent_loaded * 100)) + " percent loaded")

    def unload_chunk(self, coords):
        if coords in self.chunks.keys() and self.chunks[coords].loaded:
            if coords in self.surfaces.keys():
                self.surfaces.pop(coords)
            for k in self.chunks[coords].tiledict.keys():
                self.global_tiledict.pop(self.chunks[coords].tiledict[k].pos)
            self.chunks.pop(coords)

    def chunks_loadingupdate(self):
        center = (int(player.world_pos[0] / CHUNKSIZE), int(player.world_pos[1] / CHUNKSIZE))
        for x in range(center[0] - CHUNKLOAD_RADIUS - 1, center[0] + CHUNKLOAD_RADIUS + 1):
            for y in range(center[1] - CHUNKLOAD_RADIUS - 1, center[1] + CHUNKLOAD_RADIUS + 1):
                if (x, y) not in self.chunks.keys():
                    self.load_chunk((x, y))
        keys = list(self.chunks.keys()).copy()
        for k in keys:
            if k[0] not in range(center[0] - CHUNKLOAD_RADIUS - 3, center[0] + CHUNKLOAD_RADIUS + 3)\
                    or k[1] not in range(center[1] - CHUNKLOAD_RADIUS - 3, center[1] + CHUNKLOAD_RADIUS + 3):
                self.unload_chunk(k)

    def get_tile_id(self, x, y):
        if (x, y) in self.global_tiledict.keys():
            return self.global_tiledict[x, y].id
        else:
            return None


def enemy_choose(x):
    r = numpy.random.random()
    f = min(1, numpy.exp(-x/30))
    temp = numpy.exp((25 - x) / 10)
    g = max(0, (temp / numpy.power(1 + temp, 2) * 2.9) - (numpy.exp(2.5) / numpy.power(1 + numpy.exp(2.5), 2) * 2.9)) + f
    if r < f:
        return normal_enemy
    elif f < r < g:
        return elite_enemy
    else:
        return boss_enemy


class PhysicsEntity(pg.sprite.Sprite):
    def __init__(self, pos, vel, lifetime, image, team, rebound, stats):
        pg.sprite.Sprite.__init__(self)
        self.world_pos = pos
        self.lifetime = lifetime
        self.image = image
        self.team = team
        self.rebound = rebound
        self.vectors = []
        self.time = time.perf_counter()
        self.proj_cd = time.perf_counter()
        self.rect = pg.Rect(W / 2, H / 2, SCALING, SCALING)
        self.stats = stats
        velmult = hypot(vel[0], vel[1]) / stats.speed
        self.vel = [vel[0] / velmult, vel[1] / velmult] if velmult != 0 else vel
        self.rect = pg.Rect((0, 0, 1, 1))
        self.flipped = False

    def update(self):
        if hypot(self.world_pos[0] - player.world_pos[0], self.world_pos[1] - player.world_pos[1]) > CHUNKSIZE * (CHUNKLOAD_RADIUS + 2):
            self.groups()[0].remove(self)
        else:
            dt = time.perf_counter() - self.time
            for i in range(PHYS_TIMESTEP):
                self.physics_update(dt / PHYS_TIMESTEP)
                if self.stats.str not in ["PLR_P", "NP", "EP"]:
                    self.collide(projectileGroup)
                if self.stats.str in ["N", "E", "B"]:
                    self.collide(playerGroup)
                self.stats.update(dt / PHYS_TIMESTEP)
                self.rect_calc()
            self.time = time.perf_counter()
            if self.lifetime != -1:
                self.lifetime -= dt
                if self.lifetime < 0 < len(self.groups()):
                    self.groups()[0].remove(self)
            if self.stats.str in ["N", "E", "B"] and self.stats.hp <= 0 < len(self.groups()):
                player_stats.xp += 2 if self.stats.str == "N" else (40 if self.stats.str == "E" else 300)
                self.groups()[0].remove(self)
            if self.stats.str in ["N", "E", "B"] and time.perf_counter() - self.proj_cd > self.stats.fire_rate:
                proj = enemy_projectile_normal if self.stats.str == "N" else enemy_projectile_strong
                extras = [self.world_pos[0] - player.world_pos[0], self.world_pos[1] - player.world_pos[1],
                          -proj.grav, proj.speed]
                if hypot(extras[0], extras[1]) < 80:
                    theta = zero(proj_func, (0, numpy.pi / 4), 10, extras)
                    if theta is not None:
                        direction = [numpy.cos(theta), numpy.sin(theta)]
                        projectileGroup.add(PhysicsEntity([self.world_pos[0] + (direction[0] / 50), self.world_pos[1] +
                                (direction[1] / 50) - 0.7],  direction, 5, sprites["tile_red"], 1, 1.3, proj.__copy__()))
                    self.proj_cd = time.perf_counter()

    def rect_calc(self):
        if self.stats.str in ["PLR_P", "NP"]:
            self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2 + SCALING / 4,
                    (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2 + SCALING / 4, SCALING / 2, SCALING / 2)
        elif self.stats.str == "EP":
            self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2,
                    (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2, SCALING, SCALING)
        elif self.stats.str == "E":
            self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2 - SCALING * .3,
                    (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2 - SCALING * 2.2, SCALING * 1.6, SCALING * 3.2)
        elif self.stats.str == "B":
            self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2 - SCALING,
                    (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2 - SCALING * 5, SCALING * 3, SCALING * 6)
            hp = Bar(pg.Rect(self.rect.left - (SCALING * 3), self.rect.top - (SCALING * 2), self.rect.width +
                    SCALING * 6, SCALING), (pg.Color("red"), pg.Color("white")), False)
            hp.render(self.stats.hp, self.stats.max_hp)
        elif self.stats.str == "N":
            self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2,
                    (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2 - SCALING, SCALING, SCALING * 2)
        elif self.stats.str == "PLR":
            self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2 - SCALING / 2,
                    (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2 - SCALING * 2, SCALING * 2, SCALING * 3)
        if self.image.get_height() != self.rect.height:
            self.image = pg.transform.scale(self.image, (self.rect.width, self.rect.height))
        if (self.vel[0] < 0) != self.flipped:
            self.image = pg.transform.flip(self.image, True, False)
            self.flipped = not self.flipped

    def physics_update(self, mult):
        self.vel[1] += self.stats.grav * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                if hypot(self.vel[0], self.vel[1]) > 5:
                    while [0, 0] in self.vectors:
                        self.world_pos[0] -= self.vel[0] * 0.01
                        self.world_pos[1] -= self.vel[1] * 0.01
                        self.vector_recalc()
                else:
                    self.world_pos[1] -= 1
            if [0, 1] in self.vectors or [0, -1] in self.vectors:
                self.vel[1] /= -self.rebound
                self.vel[0] /= self.rebound
                self.world_pos[1] -= 0.2 * (-1 if [0, -1] in self.vectors else 1)
            if [1, 0] in self.vectors or [-1, 0] in self.vectors:
                self.vel[0] /= -self.rebound
                self.vel[1] /= self.rebound
                self.world_pos[0] -= 0.2 * (-1 if [-1, 0] in self.vectors else 1)
        self.vel[0] /= 1 + (.1 * mult)
        self.world_pos[0] += self.vel[0] * mult
        self.world_pos[1] += self.vel[1] * mult

    def vector_recalc(self):
        tolerance = 0.01
        self.vectors = []
        xb = round(self.world_pos[0])
        yb = round(self.world_pos[1])
        for x in range(xb - 1, xb + 2):
            for y in range(yb - 1, yb + 2):
                if xb - self.world_pos[0] < -tolerance and x - xb == -1:
                    continue
                if xb - self.world_pos[0] > tolerance and x - xb == 1:
                    continue
                if yb - self.world_pos[1] < -tolerance and y - yb == -1:
                    continue
                if yb - self.world_pos[1] > tolerance and y - yb == 1:
                    continue
                if (x, y) not in world.global_tiledict.keys() or ((x, y) in world.global_tiledict.keys() and world.get_tile_id(x, y) == 0):
                    self.vectors.append([x - xb, y - yb])

    def collide(self, group: pg.sprite.Group):
        sprites = pg.sprite.spritecollide(self, group, False)
        for s in sprites:
            if s.team != self.team:
                self.stats.damage(s.stats)
                if s.stats.str in ["PLR_P", "NP", "EP"] and len(s.groups()) > 0:
                    s.remove(s.groups()[0])


def zero(func, bounds, points, extras):
    delta = (bounds[1] - bounds[0]) / points
    p1 = [0, func(0, extras)]
    p2 = [delta, func(delta, extras)]
    tempbool = False
    for i in range(points):
        if numpy.sign(p1[1]) != numpy.sign(p2[1]):
            tempbool = True
            break
        p1[0] += delta
        p2[0] += delta
        p1[1] = func(p1[0], extras)
        p2[1] = func(p2[0], extras)
    if tempbool:
        p3 = [(p1[0] + p2[0]) / 2, func((p1[0] + p2[0]) / 2, extras)]
        while p3[1] > 0.01:
            if numpy.sign(p1[1]) != numpy.sign(p3[1]):
                p2 = p3
            elif numpy.sign(p2[1]) != numpy.sign(p3[1]):
                p1 = p3
            else:
                return None
            p3 = [(p1[0] + p2[0]) / 2, func((p1[0] + p2[0]) / 2, extras)]
        return p3[1]
    return None


def proj_func(t, extras):
    return extras[0] * numpy.tan(t) - (extras[3] * extras[0] ** 2) / (2 * extras[2] ** 2 * (numpy.cos(t)) ** 2) + extras[1]


class Player (PhysicsEntity):
    def physics_update(self, mult):
        if pg.key.get_pressed()[pg.K_a]:
            self.vel[0] -= (self.stats.speed if [0, 1] in self.vectors else self.stats.speed / 4) * mult
        if pg.key.get_pressed()[pg.K_d]:
            self.vel[0] += (self.stats.speed if [0, 1] in self.vectors else self.stats.speed / 4) * mult
        if pg.key.get_pressed()[pg.K_SPACE] and [0, 1] in self.vectors:
            self.vel[1] -= self.stats.jump
            self.world_pos[1] -= .05
        self.vel[1] += self.stats.grav * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                if hypot(self.vel[0], self.vel[1]) > 5:
                    while [0, 0] in self.vectors:
                        self.world_pos[0] -= self.vel[0] * 0.01
                        self.world_pos[1] -= self.vel[1] * 0.01
                        self.vector_recalc()
                else:
                    self.world_pos[1] -= 1
            if [0, 1] in self.vectors:
                while [0, 1] in self.vectors:
                    self.world_pos[1] -= 0.01
                    self.vector_recalc()
                self.world_pos[1] += 0.01
                self.vector_recalc()
                self.vel[1] = 0
                if (self.vel[0] < 0 and pg.key.get_pressed()[pg.K_d]) or (
                        self.vel[0] > 0 and pg.key.get_pressed()[pg.K_a]) or (
                        not pg.key.get_pressed()[pg.K_a] and not pg.key.get_pressed()[pg.K_d]):
                    self.vel[0] /= 1 + (10 * mult)
                else:
                    self.vel[0] /= 1 + (3 * mult)
            if [0, -1] in self.vectors:
                self.vel[1] /= -self.rebound
                self.world_pos[1] += 0.2
            if [1, 0] in self.vectors or [-1, 0] in self.vectors:
                if [0, 1] in self.vectors:
                    if self.vel[0] < 0 and world.get_tile_id(round(self.world_pos[0]) - 1, round(self.world_pos[1]) - 1) == 0:
                        self.world_pos[1] -= 1
                    else:
                        self.world_pos[0] -= -0.2
                    if self.vel[0] > 0 and world.get_tile_id(round(self.world_pos[0]) + 1, round(self.world_pos[1]) - 1) == 0:
                        self.world_pos[1] -= 1
                    else:
                        self.world_pos[0] -= 0.2
                else:
                    self.vel[0] /= -self.rebound
                    self.world_pos[0] -= 0.2 * (-1 if [-1, 0] in self.vectors else 1)

        else:
            self.vel[0] /= 1 + (.1 * mult)
        self.world_pos[0] += self.vel[0] * mult
        self.world_pos[1] += self.vel[1] * mult


class Enemy (PhysicsEntity):
    def physics_update(self, mult):
        if hypot(self.world_pos[0] - player.world_pos[0], self.world_pos[1] - player.world_pos[1]) < 100 and player.world_pos[0] < self.world_pos[0]:
            self.vel[0] -= (self.stats.speed if [0, 1] in self.vectors else self.stats.speed / 4) * mult
        elif hypot(self.world_pos[0] - player.world_pos[0], self.world_pos[1] - player.world_pos[1]) < 100 and player.world_pos[0] > self.world_pos[0]:
            self.vel[0] += (self.stats.speed if [0, 1] in self.vectors else self.stats.speed / 4) * mult
        if hypot(self.world_pos[0] - player.world_pos[0], self.world_pos[1] - player.world_pos[1]) < 100 and [0, 1] in self.vectors and player.world_pos[1] < self.world_pos[1] and \
                (world.get_tile_id(round(self.world_pos[0]) - numpy.sign(self.vel[0]), round(self.world_pos[1]) + 1) != 0 or
                world.get_tile_id(round(self.world_pos[0]) - numpy.sign(self.vel[0]),
                round(self.world_pos[1]) - 1) == 0):
            self.vel[1] -= self.stats.jump
            self.world_pos[1] -= .05
        self.vel[1] += self.stats.grav * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                if hypot(self.vel[0], self.vel[1]) > 5:
                    while [0, 0] in self.vectors:
                        self.world_pos[0] -= self.vel[0] * 0.01
                        self.world_pos[1] -= self.vel[1] * 0.01
                        self.vector_recalc()
                else:
                    self.world_pos[1] -= 1
            if [0, 1] in self.vectors:
                while [0, 1] in self.vectors:
                    self.world_pos[1] -= 0.01
                    self.vector_recalc()
                self.world_pos[1] += 0.01
                self.vector_recalc()
                self.vel[1] = 0
                if (self.vel[0] < 0 and player.world_pos[0] > self.world_pos[0]) or (
                        self.vel[0] > 0 and player.world_pos[0] < self.world_pos[0]) or (
                        not player.world_pos[0] < self.world_pos[0] and not player.world_pos[0] > self.world_pos[0]):
                    self.vel[0] /= 1 + (10 * mult)
                else:
                    self.vel[0] /= 1 + (3 * mult)
            if [0, -1] in self.vectors:
                self.vel[1] /= -self.rebound
                self.world_pos[1] += 0.2
            if [1, 0] in self.vectors or [-1, 0] in self.vectors:
                if [0, 1] in self.vectors:
                    if self.vel[0] < 0 and world.get_tile_id(
                            round(self.world_pos[0]) - 1, round(self.world_pos[1])) == 0:
                        self.world_pos[1] -= 1
                    else:
                        self.world_pos[0] -= -0.2
                    if self.vel[0] > 0 and world.get_tile_id(
                            round(self.world_pos[0]) + 1, round(self.world_pos[1])) == 0:
                        self.world_pos[1] -= 1
                    else:
                        self.world_pos[0] -= 0.2
                else:
                    self.vel[0] /= -self.rebound
                    self.world_pos[0] -= 0.2 * (-1 if [-1, 0] in self.vectors else 1)

        else:
            self.vel[0] /= 1 + (.1 * mult)
        self.world_pos[0] += self.vel[0] * mult
        self.world_pos[1] += self.vel[1] * mult


class ProjStats:
    def __init__(self, str, dmg, pierce, speed, grav):
        self.str = str
        self.dmg = dmg
        self.pierce = pierce
        self.speed = speed
        self.grav = grav

    def update(self, dt):
        pass

    def __copy__(self):
        return ProjStats(self.str, self.dmg, self.pierce, self.speed, self.grav)


class EnemyStats:
    def __init__(self, str, max_hp, regen, armor, speed, grav, jump, contact_damage, fire_rate):
        self.str = str
        self.hp = max_hp
        self.max_hp = max_hp
        self.regen = regen
        self.armor = armor
        self.speed = speed
        self.grav = grav
        self.jump = jump
        self.contact_damage = contact_damage
        self.contact_damage_cd = time.perf_counter()
        self.fire_rate = fire_rate

    def damage(self, stats):
        if stats.str in ["PLR_P", "EP", "NP"]:
            self.hp -= stats.dmg * numpy.float_power(.95, self.armor - stats.pierce)
        else:
            if time.perf_counter() - self.contact_damage_cd > CONTACT_CD:
                self.contact_damage_cd = time.perf_counter()
                self.hp -= stats.contact_damage * numpy.float_power(.95, self.armor) * CONTACT_CD
                stats.hp -= self.contact_damage * numpy.float_power(.95, stats.armor) * CONTACT_CD

    def update(self, dt):
        if self.hp < self.max_hp - self.regen * dt:
            self.hp += self.regen * dt
        elif self.hp < self.max_hp:
            self.hp = self.max_hp

    def __copy__(self):
        return EnemyStats(self.str, self.max_hp, self.regen, self.armor, self.speed, self.grav, self.jump, self.contact_damage, self.fire_rate)


class PlayerStats:
    def __init__(self):
        self.defense = 0
        self.agility = 0
        self.firepower = 0
        self.marksmanship = 0
        self.accuracy = 0
        self.xp = 5000
        self.lvl = 0
        self.points = 0

    def stats_recalc(self):
        if self.xp >= numpy.power(self.lvl + 1, 2) * 5:
            self.lvl += 1
            self.points += 2
            self.xp -= numpy.power(self.lvl, 2) * 5
        player.stats.max_hp = 100 + self.defense * 25
        player.stats.armor = 5 * self.defense
        player.stats.regen = 2 + self.defense * .75
        player.stats.speed = 120 + 10 * self.agility * numpy.power(.9, self.defense)
        player.stats.jump = 50 + 5 * self.agility * numpy.power(.9, self.defense)
        player.stats.fire_rate = .5 / (numpy.exp(self.firepower / -10) * (1 + 0.2 * self.marksmanship))
        player_projectile.dmg = 50 + 10 * self.firepower
        player_projectile.pierce = 3 * self.marksmanship
        player_projectile.speed = (100 + 20 * self.marksmanship) * numpy.exp(self.firepower / -20)
        player_projectile.grav = (60 + 10 * self.marksmanship) * numpy.exp(self.firepower / -25)
        self.accuracy = numpy.exp(self.marksmanship / -4) / 10


class UI:
    def __init__(self):
        pass

    def render(self):
        f = pg.font.SysFont("Arial", 15)
        r = f.render(str(int(sum(fpsArr) / len(fpsArr))), True, pg.Color("red"))
        SURF.blit(r, (5, 5))
        if not initial_load:
            player.time = time.perf_counter()
            loading_bar = Bar(pg.Rect(int(W * .25), int(H * .454), int(W * .5), int(H * .1)), (pg.Color("blue"), pg.Color("white")), False)
            loading_bar.render(world.percent_loaded, 1)
        else:
            healthbar = Bar(pg.Rect(int(W * .823), int(W * .01), int(W * .166), int(W * .02)), (pg.Color("red"), pg.Color("white")), True)
            healthbar.render(player.stats.hp, player.stats.max_hp)
            exp_bar = Bar(pg.Rect(int(W * .823), int(W * .033), int(W * .166), int(W * .02)), (pg.Color("cyan"), pg.Color("white")), True)
            exp_bar.render(player_stats.xp, numpy.power(player_stats.lvl + 1, 2) * 5)
            if UI_bool:
                for b in buttons:
                    b.render()
                f = pg.font.SysFont("Arial", int(W * .028))
                r = f.render("Marksmanship: " + str(player_stats.marksmanship), True, pg.Color("white"))
                SURF.blit(r, (W * .935 - r.get_width(), H - W * .052 + (W * .04 - r.get_height()) / 2))
                r = f.render("Firepower: " + str(player_stats.firepower), True, pg.Color("white"))
                SURF.blit(r, (W * .935 - r.get_width(), H - W * .105 + (W * .04 - r.get_height()) / 2))
                r = f.render("Agility: " + str(player_stats.agility), True, pg.Color("white"))
                SURF.blit(r, (W * .935 - r.get_width(), H - W * .157 + (W * .04 - r.get_height()) / 2))
                r = f.render("Defense: " + str(player_stats.defense), True, pg.Color("white"))
                SURF.blit(r, (W * .935 - r.get_width(), H - W * .21 + (W * .04 - r.get_height()) / 2))
                r = f.render("Points: " + str(player_stats.points), True, pg.Color("white"))
                SURF.blit(r, (W * .987 - r.get_width(), H - W * .262 + (W * .04 - r.get_height()) / 2))
            else:
                if player_stats.points > 0:
                    f = pg.font.SysFont("Arial", int(W * .013))
                    r = f.render("Press [TAB] for upgrades!", True, pg.Color("white"))
                    SURF.blit(r, (W * .987 - r.get_width(), W * .056))


class Bar:
    def __init__(self, rect: pg.Rect, colors, text):
        self.rect = rect
        self.colors = colors
        self.text = text

    def render(self, value, max_value):
        width = max(0, int(self.rect.width * (max(0.0001, value) / max_value)))
        pg.draw.rect(SURF, self.colors[0], pg.Rect(self.rect.left, self.rect.top, width, self.rect.height))
        pg.draw.rect(SURF, self.colors[1], pg.Rect(self.rect.left + width, self.rect.top, self.rect.width - width, self.rect.height))
        if self.text:
            f = pg.font.SysFont("Arial", int(self.rect.height * .65))
            r = f.render(str(int(value * 10) / 10) + " / " + str(int(max_value * 10) / 10), True, pg.Color("black"))
            SURF.blit(r, (self.rect.left + self.rect.width / 2 - r.get_width() / 2, self.rect.top + self.rect.height / 2 - r.get_height() / 2))


class Button:
    def __init__(self, rect: pg.Rect, color, text, func, params):
        self.rect = rect
        self.color = color
        self.text = text
        self.func = func
        self.params = params

    def render(self):
        pg.draw.rect(SURF, self.color, self.rect)
        f = pg.font.SysFont("Arial", int(self.rect.height * .7))
        r = f.render(self.text, True, pg.Color("black"))
        SURF.blit(r, (self.rect.left + self.rect.width / 2 - r.get_width() / 2, self.rect.top + self.rect.height / 2 - r.get_height() / 2))


if __name__ == '__main__':
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pg.init()
    clock = pg.time.Clock()
    W = pg.display.Info().current_w
    H = pg.display.Info().current_h
    SURF = pg.display.set_mode((W, H), pg.NOFRAME)

    FPS = 60
    CHUNKLOAD_RADIUS = 4
    CHUNKSIZE = 64
    SCALING = 15
    PHYS_TIMESTEP = 4
    ENEMIES_PER_CHUNK = 2
    CONTACT_CD = 1

    sprites = {
        "tile_dark": pg.transform.scale(pg.image.load("sprites\\tile_dark.png"), (SCALING, SCALING)),
        "tile_light": pg.transform.scale(pg.image.load("sprites\\tile_light.png"), (SCALING, SCALING)),
        "tile_blue": pg.transform.scale(pg.image.load("sprites\\tile_blue.png"), (SCALING, SCALING)),
        "tile_red":  pg.transform.scale(pg.image.load("sprites\\tile_red.png"), (SCALING, SCALING)),
        "tile_green": pg.transform.scale(pg.image.load("sprites\\tile_green.png"), (SCALING, SCALING)),
        "player": pg.transform.scale(pg.image.load("sprites\\player.png"), (int(SCALING * 1.4), SCALING * 2))
    }

    fpsArr = [1] * 10
    timer = 0
    initial_load = False
    projtimer = 0
    UI_bool = False
    buttons = []

    playerGroup = pg.sprite.Group()
    projectileGroup = pg.sprite.Group()
    enemyGroup = pg.sprite.Group()

    normal_enemy = EnemyStats("N", 150, 2, 0, 100, 100, 30, 10, 2)
    elite_enemy = EnemyStats("E", 1000, 10, 30, 30, 100, 20, 100, 1.5)
    boss_enemy = EnemyStats("B", 10000, 50, 80, 30, 100, 10, 1000000, .3)
    enemy_projectile_normal = ProjStats("NP", 20, 5, 50, 60)
    enemy_projectile_strong = ProjStats("EP", 80, 20, 30, 40)
    player_projectile = ProjStats("PLR_P", 20, 0, 100, 60)

    N = Noise()
    world = World()
    player = Player([0, 0], [0, 0], -1, sprites["player"], 0, 10000, EnemyStats("PLR", 100, 2, 20, 120, 100, 50, 20, 1))
    playerGroup.add(player)
    player_stats = PlayerStats()
    UI = UI()
    thread = Thread(target=world.load_all)
    thread.start()

    def stat_up(params):
        if player_stats.points > 0:
            vars(player_stats)[params[0]] += 1
            player_stats.points -= 1
    buttons.append(Button(pg.Rect(W * .947, H - W * .052, W * .04, W * .04), pg.Color("white"), "+", stat_up, ["marksmanship"]))
    buttons.append(Button(pg.Rect(W * .947, H - W * .105, W * .04, W * .04), pg.Color("white"), "+", stat_up, ["firepower"]))
    buttons.append(Button(pg.Rect(W * .947, H - W * .157, W * .04, W * .04), pg.Color("white"), "+", stat_up, ["agility"]))
    buttons.append(Button(pg.Rect(W * .947, H - W * .21, W * .04, W * .04), pg.Color("white"), "+", stat_up, ["defense"]))
    while True:
        timer = time.perf_counter()
        for event in pg.event.get():
            if event.type == pg.QUIT or event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                k = event.key
                if k == pg.K_TAB:
                    UI_bool = not UI_bool
            if event.type == pg.MOUSEBUTTONDOWN:
                if pg.mouse.get_pressed(3)[2]:
                    player.world_pos = [player.world_pos[0] + (pg.mouse.get_pos()[0] - (W / 2)) / SCALING,
                        player.world_pos[1] + (pg.mouse.get_pos()[1] - (H / 2)) / SCALING]
                elif pg.mouse.get_pressed(3)[0] and UI_bool:
                    for b in buttons:
                        if b.rect.left <= pg.mouse.get_pos()[0] <= b.rect.right and\
                                b.rect.top <= pg.mouse.get_pos()[1] <= b.rect.bottom:
                            b.func(b.params)
        SURF.fill((0, 0, 0))
        if not initial_load and world.loading_check():
            initial_load = True
            for e in enemyGroup:
                e.time = time.perf_counter()
        if initial_load:
            world.chunks_loadingupdate()
            for c in world.chunks.values():
                c.draw()
            if pg.mouse.get_pressed(3)[0]:
                if timer - projtimer > 1 / player.stats.fire_rate and not UI_bool:
                    direction = [(pg.mouse.get_pos()[0] - (W / 2)) / W, (pg.mouse.get_pos()[1] - (H / 2)) / H]
                    direction[0] += (numpy.random.random() - .5) * player_stats.accuracy * hypot(direction[0], direction[1]) * 2
                    direction[1] += (numpy.random.random() - .5) * player_stats.accuracy * hypot(direction[0], direction[1]) * 2
                    projectileGroup.add(PhysicsEntity([player.world_pos[0] + (direction[0] / 50),
                        player.world_pos[1] + (direction[1] / 50) - 0.7], direction, 5, sprites["tile_red"], 0, 1.3, player_projectile.__copy__()))
                    projtimer = timer
            projectileGroup.update()
            projectileGroup.draw(SURF)
            enemyGroup.update()
            enemyGroup.draw(SURF)
            playerGroup.update()
            playerGroup.draw(SURF)
            if player.stats.hp < 0:
                player.stats.hp = 0
            player_stats.stats_recalc()
        UI.render()
        pg.display.update()
        clock.tick(FPS)
        fpsArr.append(1 / (time.perf_counter() - timer))
        del fpsArr[0]

"""
TODO:
-broken autostep
-da boss healthbar is rendered during physics calculation, which causes some funky issues
-balancing
-the game sucks. boring to play. progression is bad.
-no graphics (will not fix)
-messy code (not an issue just yet)
"""