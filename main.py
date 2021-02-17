import pygame as pg
import time, sys, os, numpy
from multiprocessing.pool import Pool
from noise import Noise
from threading import Thread


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
                    a = world.get_tile_id(tile.pos[0] - 1, tile.pos[1]) == 1 or world.get_tile_id(tile.pos[0] + 1, tile.pos[1]) == 1 or  world.get_tile_id(tile.pos[0], tile.pos[1] + 1) == 1 or  world.get_tile_id(tile.pos[0], tile.pos[1] - 1) == 1
                    surface.blit((tile_green if a else tile_dark) if tile.id == 0 else tile_light, (k[0], k[1]))
                surface = pg.transform.scale(surface, (CHUNKSIZE * SCALING, CHUNKSIZE * SCALING))
                world.surfaces.update({self.pos: surface})
            SURF.blit(world.surfaces[self.pos], ((self.pos[0] * CHUNKSIZE - player.world_pos[0]) * SCALING + int(W / 2), (self.pos[1] * CHUNKSIZE - player.world_pos[1]) * SCALING + int(H / 2)))


class World:
    def __init__(self):
        self.pool = Pool()
        self.chunks = {}
        self.cached_chunks = {}
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
        if coords in self.cached_chunks.keys():
            self.chunks.update({coords: self.cached_chunks.pop(coords)})
            for t in self.chunks[coords].tiledict.values():
                self.global_tiledict.update({(t.pos[0], t.pos[1]): t})
        else:
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
        self.loading_check()
        print(str(int(self.percent_loaded * 100)) + " percent loaded")

    def unload_chunk(self, coords):
        if coords in self.chunks.keys() and self.chunks[coords].loaded:
            self.cached_chunks.update({coords: self.chunks.pop(coords)})
            self.cached_chunks[coords].loaded = False
            if coords in self.surfaces.keys():
                self.surfaces.pop(coords)
            for k in self.cached_chunks[coords].tiledict.keys():
                self.global_tiledict.pop(self.cached_chunks[coords].tiledict[k].pos)

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


class PhysicsEntity(pg.sprite.Sprite):
    def __init__(self, pos, vel, lifetime, image, team, gravity, rebound):
        pg.sprite.Sprite.__init__(self)
        self.world_pos = pos
        self.vel = vel
        self.lifetime = lifetime
        self.image = image
        self.team = team
        self.gravity = gravity
        self.rebound = rebound
        self.vectors = []
        self.time = time.perf_counter()
        self.rect = pg.Rect(W / 2, H / 2, SCALING, SCALING)

    def update(self):
        dt = time.perf_counter() - self.time
        for i in range(PHYS_RATE):
            self.physics_update(dt / PHYS_RATE)
            self.collide(projectileGroup)
        self.time = time.perf_counter()
        self.rect = pg.Rect((self.world_pos[0] - player.world_pos[0]) * SCALING + W / 2,
                (self.world_pos[1] - player.world_pos[1]) * SCALING + H / 2, SCALING, SCALING)

    def physics_update(self, mult):
        if self.lifetime != -1:
            self.lifetime -= mult
            if self.lifetime < 0:
                projectileGroup.remove(self)
        self.vel[1] += self.gravity * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
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
                group.remove(s)
                self.remove(self.groups()[0])


class Player (PhysicsEntity):
    def physics_update(self, mult):
        if pg.key.get_pressed()[pg.K_a]:
            self.vel[0] -= (30 if [0, 1] in self.vectors else 8) * mult
        if pg.key.get_pressed()[pg.K_d]:
            self.vel[0] += (30 if [0, 1] in self.vectors else 8) * mult
        if pg.key.get_pressed()[pg.K_SPACE] and [0, 1] in self.vectors:
            self.vel[1] -= 40
            self.world_pos[1] -= .05
        self.vel[1] += self.gravity * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                self.world_pos[1] -= 1
            if [0, 1] in self.vectors:
                while [0, 1] in self.vectors:
                    self.world_pos[1] -= 0.006
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
                    if self.vel[0] < 0 and world.get_tile_id(round(self.world_pos[0]) - 1, round(self.world_pos[1])) == 0:
                        self.world_pos[1] -= 1
                    else:
                        self.world_pos[0] -= -0.2
                    if self.vel[0] > 0 and world.get_tile_id(round(self.world_pos[0]) + 1, round(self.world_pos[1])) == 0:
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


class Enemy (Player):
    def physics_update(self, mult):
        if player.world_pos[0] < self.world_pos[0]:
            self.vel[0] -= (25 if [0, 1] in self.vectors else 7) * mult
        elif player.world_pos[0] > self.world_pos[0]:
            self.vel[0] += (25 if [0, 1] in self.vectors else 7) * mult
        if [0, 1] in self.vectors and player.world_pos[1] < self.world_pos[1] and \
                (world.get_tile_id(round(self.world_pos[0]) - numpy.sign(self.vel[0]), round(self.world_pos[1]) + 1) != 0 or
                world.get_tile_id(round(self.world_pos[0]) - numpy.sign(self.vel[0]),
                round(self.world_pos[1]) - 1) == 0):
            self.vel[1] -= 50
            self.world_pos[1] -= .05
        self.vel[1] += self.gravity * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                self.world_pos[1] -= 1
            if [0, 1] in self.vectors:
                while [0, 1] in self.vectors:
                    self.world_pos[1] -= 0.006
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


if __name__ == '__main__':
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pg.init()
    clock = pg.time.Clock()
    W = pg.display.Info().current_w
    H =  pg.display.Info().current_h
    SURF = pg.display.set_mode((W, H), pg.NOFRAME)

    FPS = 120
    CHUNKLOAD_RADIUS = 4
    CHUNKSIZE = 64
    SCALING = 5
    PHYS_RATE = 10

    sprites = {
        "tile_dark": pg.transform.scale(pg.image.load("sprites\\tile_dark.png"), (SCALING, SCALING)),
        "tile_light": pg.transform.scale(pg.image.load("sprites\\tile_light.png"), (SCALING, SCALING)),
        "tile_blue": pg.transform.scale(pg.image.load("sprites\\tile_blue.png"), (SCALING, SCALING)),
        "tile_red":  pg.transform.scale(pg.image.load("sprites\\tile_red.png"), (SCALING, SCALING)),
        "tile_green": pg.transform.scale(pg.image.load("sprites\\tile_green.png"), (SCALING, SCALING))
    }

    fpsArr = [1] * FPS
    timer = 0
    initial_load = False

    playerGroup = pg.sprite.Group()
    projectileGroup = pg.sprite.Group()
    enemyGroup = pg.sprite.Group()

    N = Noise()
    world = World()
    player = Player([0, 0], [0, 0], -1, sprites["tile_blue"], 0, 40, 10000)
    playerGroup.add(player)
    thread = Thread(target=world.load_all)
    thread.start()
    while True:
        timer = time.perf_counter()
        for event in pg.event.get():
            if event.type == pg.QUIT or event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                k = event.key
            if event.type == pg.MOUSEBUTTONDOWN:
                direction = [(pg.mouse.get_pos()[0] - (W / 2)) * 200 / W, (pg.mouse.get_pos()[1] - (H / 2)) * 200 / H]
                if pg.mouse.get_pressed(3)[0]:
                    projectileGroup.add(PhysicsEntity([player.world_pos[0] + (direction[0] / 50),
                        player.world_pos[1] + (direction[1] / 50)], [direction[0] + player.vel[0], direction[1] + player.vel[1]], 5, sprites["tile_red"], 2, 50, 1.3))
                else:
                    enemyGroup.add(Enemy([player.world_pos[0] + (pg.mouse.get_pos()[0] - (W / 2)) / SCALING,
                        player.world_pos[1] + (pg.mouse.get_pos()[1] - (H / 2)) / SCALING], [player.vel[0], player.vel[1]], -1, sprites["tile_blue"], 1, 50, 1.3))

        SURF.fill((0, 0, 0))
        initial_load = initial_load or world.loading_check()
        if initial_load:
            world.chunks_loadingupdate()
            for c in world.chunks.values():
                c.draw()
            projectileGroup.update()
            projectileGroup.draw(SURF)
            enemyGroup.update()
            enemyGroup.draw(SURF)
            playerGroup.update()
            playerGroup.draw(SURF)
        else:
            player.time = time.perf_counter()
            f = pg.font.SysFont("Arial", 100, bold=True)
            r = f.render(str(int(world.percent_loaded * 100)) + "% loaded", True, pg.Color("white"))
            SURF.blit(r, ((W / 2) - r.get_width() / 2, (H / 2) - r.get_height() / 2))
        f = pg.font.SysFont("Arial", 15)
        r = f.render(str(int(sum(fpsArr) / len(fpsArr))), True, pg.Color("red"))
        SURF.blit(r, (5, 5))

        pg.display.update()
        clock.tick(FPS)
        fpsArr.append(1 / (time.perf_counter() - timer))
        del fpsArr[0]
