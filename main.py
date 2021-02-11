import pygame as pg
import time, sys, os
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
        print(time.perf_counter())
        return self

    def draw(self):
        if self.loaded:
            if self.pos not in world.surfaces.keys():
                surface = pg.Surface((CHUNKSIZE * SCALING, CHUNKSIZE * SCALING))
                for k in self.tiledict.keys():
                    surface.blit(sprites["tile_dark"] if self.tiledict[k].id == 0 else sprites["tile_light"], (k[0] * SCALING, k[1] * SCALING))
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
        self.chunks.update({(0, 0): Chunk((0, 0))})

    def loading_check(self):
        for c in self.chunks.values():
            if not c.loaded:
                return False
        return True

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

    def unload_chunk(self, coords):
        if coords in self.chunks.keys() and self.chunks[coords].loaded:
            self.cached_chunks.update({coords: self.chunks.pop(coords)})
            self.cached_chunks[coords].loaded = False
            if coords in self.surfaces.keys():
                self.surfaces.pop(coords)
            for k in self.cached_chunks[coords].tiledict.keys():
                self.global_tiledict.pop(self.cached_chunks[coords].tiledict[k].world_pos)


    def chunks_loadingupdate(self):
        center = (int(player.world_pos[0] / CHUNKSIZE), int(player.world_pos[1] / CHUNKSIZE))
        for x in range(center[0] - CHUNKLOAD_RADIUS - 1, center[0] + CHUNKLOAD_RADIUS + 1):
            for y in range(center[1] - CHUNKLOAD_RADIUS - 1, center[1] + CHUNKLOAD_RADIUS + 1):
                if (x, y) not in self.chunks.keys():
                    self.load_chunk((x, y))
        keys = list(self.chunks.keys()).copy()
        for k in keys:
            if k[0] not in range(center[0] - CHUNKLOAD_RADIUS - 2, center[0] + CHUNKLOAD_RADIUS + 2)\
                or k[1] not in range(center[1] - CHUNKLOAD_RADIUS - 2, center[1] + CHUNKLOAD_RADIUS + 2):
                self.unload_chunk(k)

#data format: (pos, lifetime, image str, team)
class PhysicsEntity(pg.sprite.Sprite):
    def __init__(self, data):
        pg.sprite.Sprite.__init__(self)
        self.world_pos = data[0]
        self.vel = [0, 0]
        self.vectors = []
        self.lifetime = data[1]
        self.image = sprites[data[2]]
        self.team = data[3]

    def update(self):
        mult = 1 / (sum(fpsArr) / len(fpsArr))
        if self.lifetime != -1:
            self.lifetime -= mult
            if self.lifetime < 0:
                projectileGroup.remove(self)
        self.vel[1] += 40 * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                self.world_pos[1] -= 1
            if [0, 1] in self.vectors:
                while [0, 1] in self.vectors:
                    self.world_pos[1] -= 0.006
                    self.vector_recalc()
                self.world_pos[1] += 0.02
                self.vector_recalc()
                self.vel[1] = 0
                if (self.vel[0] < 0 and pg.key.get_pressed()[pg.K_d]) or (self.vel[0] > 0 and pg.key.get_pressed()[pg.K_a]) or (not pg.key.get_pressed()[pg.K_a] and not pg.key.get_pressed()[pg.K_d]):
                    self.vel[0] /= 1 + (10 * mult)
                else:
                    self.vel[0] /= 1 + (3 * mult)
            if [0, -1] in self.vectors:
                self.vel[1] /= -2
                self.world_pos[1] += 0.1
            if [1, 0] in self.vectors:
                self.vel[0] /= -2
                while [1, 0] in self.vectors:
                    self.world_pos[0] -= 0.006
                    self.vector_recalc()
            if [-1, 0] in self.vectors:
                self.vel[0] /= -2
                while [-1, 0] in self.vectors:
                    self.world_pos[0] += 0.006
                    self.vector_recalc()
        else:
            self.vel[0] /= 1 + (.25 * mult)
        self.world_pos[0] += self.vel[0] * mult
        self.world_pos[1] += self.vel[1] * mult

    def vector_recalc(self):
        tolerance = 0
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
                if (x, y) in world.global_tiledict and world.global_tiledict[(x, y)].id == 0:
                    self.vectors.append([x - xb, y - yb])

class Player (PhysicsEntity):
    def __init__(self, data):
        PhysicsEntity.__init__(self, data)
        self.world_pos = [CHUNKSIZE / 2, CHUNKSIZE / 2]
        self.vectors = []

    def update(self):
        mult = 1 / (sum(fpsArr) / len(fpsArr))
        if pg.key.get_pressed()[pg.K_a]:
            self.vel[0] -= 40 * mult
        if pg.key.get_pressed()[pg.K_d]:
            self.vel[0] += 40 * mult
        if pg.key.get_pressed()[pg.K_SPACE] and [0, 1] in self.vectors:
            player.vel[1] -= 50
            player.world_pos[1] -= .05
        PhysicsEntity.update(self)



if __name__ == '__main__':
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pg.init()
    clock = pg.time.Clock()
    W = pg.display.Info().current_w
    H =  pg.display.Info().current_h
    SURF = pg.display.set_mode((W, H), pg.NOFRAME)

    ##### GAMEPLAY PARAMS #####
    FPS = 120
    CHUNKLOAD_RADIUS = 3
    CHUNKSIZE = 128
    SCALING = 2

    sprites = {
        "tile_dark": pg.transform.scale(pg.image.load("sprites\\tile_dark.png"), (SCALING, SCALING)),
        "tile_light": pg.transform.scale(pg.image.load("sprites\\tile_light.png"), (SCALING, SCALING)),
        "tile_blue": pg.transform.scale(pg.image.load("sprites\\tile_blue.png"), (SCALING, SCALING)),
        "tile_red":  pg.transform.scale(pg.image.load("sprites\\tile_red.png"), (SCALING, SCALING)),
    }

    fpsArr = [1] * FPS
    timer = 0
    initial_load = False
    dt = 0

    projectileGroup = pg.sprite.Group()

    N = Noise()
    world = World()
    player = Player(([CHUNKSIZE / 2, CHUNKSIZE / 2], -1, "tile_blue", 0))
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


        SURF.fill((0, 0, 0))
        initial_load = initial_load or world.loading_check()
        if initial_load:
            if dt > 5:
                world.chunks_loadingupdate()
                dt = 0
            for c in world.chunks.values():
                c.draw()
            projectileGroup.update()
            projectileGroup.draw(SURF)
            player.update()
            SURF.blit(sprites["tile_blue"], (int(W / 2), int(H / 2)))
        f = pg.font.SysFont("Arial", 15)
        r = f.render(str(int(sum(fpsArr) / len(fpsArr))), True, pg.Color("red"))
        SURF.blit(r, (5, 5))

        pg.display.update()
        clock.tick(FPS)
        dt += (time.perf_counter() - timer)
        fpsArr.append(1 / (time.perf_counter() - timer))
        del fpsArr[0]
