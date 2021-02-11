import pygame as pg
import time, sys, numpy, os
from multiprocessing.pool import Pool
from noise import Noise
from threading import  Thread


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

    def generate(self, CHUNKSIZE, N):
        noise = numpy.zeros((N.AVG_RADIUS * 2 + CHUNKSIZE, N.AVG_RADIUS * 2 + CHUNKSIZE, 1))
        print(time.perf_counter())
        for x in range(noise.shape[0]):
            for y in range(noise.shape[1]):
                noise[x, y, 0] = N.layered_worley(x + N.AVG_RADIUS + (self.pos[0] * CHUNKSIZE), y + N.AVG_RADIUS + (self.pos[1] * CHUNKSIZE))
        print(time.perf_counter())
        for x in range(CHUNKSIZE):
            for y in range(CHUNKSIZE):
                s = self.tiledict[x, y]
                s.id = 1 if N.average_cutoff((x +N.AVG_RADIUS, y + N.AVG_RADIUS), noise) > 0 else 0
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
            SURF.blit(world.surfaces[self.pos], ((self.pos[0] * CHUNKSIZE - player.pos[0]) * SCALING + int(W / 2), (self.pos[1] * CHUNKSIZE - player.pos[1]) * SCALING + int(H / 2)))


class World:
    def __init__(self):
        self.pool = Pool()
        self.chunks = {}
        self.cached_chunks = {}
        self.surfaces = {}
        self.threads = {}
        self.global_tiledict = {}
        self.chunks.update({(0, 0): Chunk((0, 0))})

    def noise_display(self):
        arr_temp = numpy.zeros((W, H, 3))
        threads = []
        pool = Pool()
        for y in range(0, H, 10):
            threads.append(pool.apply_async(N.thread_f, (y, W)))
        for t in threads:
            r = t.get()
            a = r[0]
            diff = 10
            if H - r[1] < 10:
                diff = H - r[1]
                a = r[0][0: r[0].shape[0], 0: H - r[1]]
            arr_temp[0: W, r[1]: r[1] + diff, 0:3] = a
            surfarr = pg.surfarray.make_surface(a)
            SURF.blit(surfarr, (0, r[1]))
        if N.AVERAGE:
            threads2 = []
            for y in range(H):
                threads2.append(pool.apply_async(N.thread_avg, (y, arr_temp, W)))
            print("average")
            for t in threads2:
                r = t.get()
                surfarr = pg.surfarray.make_surface(r[0])
                SURF.blit(surfarr, (0, r[1]))

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
                self.global_tiledict.pop(self.cached_chunks[coords].tiledict[k].pos)


    def chunks_loadingupdate(self):
        center = (int(player.pos[0] / CHUNKSIZE), int(player.pos[1] / CHUNKSIZE))
        for x in range(center[0] - CHUNKLOAD_RADIUS - 1, center[0] + CHUNKLOAD_RADIUS + 1):
            for y in range(center[1] - CHUNKLOAD_RADIUS - 1, center[1] + CHUNKLOAD_RADIUS + 1):
                if (x, y) not in self.chunks.keys():
                    self.load_chunk((x, y))
        keys = list(self.chunks.keys()).copy()
        for k in keys:
            if k[0] not in range(center[0] - CHUNKLOAD_RADIUS - 2, center[0] + CHUNKLOAD_RADIUS + 2)\
                or k[1] not in range(center[1] - CHUNKLOAD_RADIUS - 2, center[1] + CHUNKLOAD_RADIUS + 2):
                self.unload_chunk(k)

#data format: (pos, lifetime, image str, team
class PhysicsEntity(pg.sprite.Sprite):
    def __init__(self, data):
        pg.sprite.Sprite.__init__(self)
        self.pos = data[0]
        self.vel = [0, 0]
        self.lifetime = data[1]
        self.image = sprites[data[2]]
        self.team = data[3]

    def update(self):
        mult = 1 / (sum(fpsArr) / len(fpsArr))
        self.vel[1] += 40 * mult
        self.vector_recalc()
        if len(self.vectors) > 0:
            if [0, 0] in self.vectors:
                self.pos[1] -= 1
            if [0, 1] in self.vectors:
                while [0, 1] in self.vectors:
                    self.pos[1] -= 0.006
                    self.vector_recalc()
                self.pos[1] += 0.02
                self.vector_recalc()
                self.vel[1] = 0
                if (self.vel[0] < 0 and pg.key.get_pressed()[pg.K_d]) or (self.vel[0] > 0 and pg.key.get_pressed()[pg.K_a]) or (not pg.key.get_pressed()[pg.K_a] and not pg.key.get_pressed()[pg.K_d]):
                    self.vel[0] /= 1 + (10 * mult)
                else:
                    self.vel[0] /= 1 + (3 * mult)
            if [0, -1] in self.vectors:
                self.vel[1] /= -2
                self.pos[1] += 0.1
            if [1, 0] in self.vectors:
                self.vel[0] /= -2
                while [1, 0] in self.vectors:
                    self.pos[0] -= 0.006
                    self.vector_recalc()
            if [-1, 0] in self.vectors:
                self.vel[0] /= -2
                while [-1, 0] in self.vectors:
                    self.pos[0] += 0.006
                    self.vector_recalc()
        else:
            self.vel[0] /= 1 + (.25 * mult)
        self.pos[0] += self.vel[0] * mult
        self.pos[1] += self.vel[1] * mult

    def vector_recalc(self):
        tolerance = 0
        self.vectors = []
        xb = round(self.pos[0])
        yb = round(self.pos[1])
        for x in range(xb - 1, xb + 2):
            for y in range(yb - 1, yb + 2):
                if xb - self.pos[0] < -tolerance and x - xb == -1:
                    continue
                if xb - self.pos[0] > tolerance and x - xb == 1:
                    continue
                if yb - self.pos[1] < -tolerance and y - yb == -1:
                    continue
                if yb - self.pos[1] > tolerance and y - yb == 1:
                    continue
                if (x, y) in world.global_tiledict and world.global_tiledict[(x, y)].id == 0:
                    self.vectors.append([x - xb, y - yb])

class Player(PhysicsEntity):
    def __init__(self, data):
        PhysicsEntity.__init__(self, data)
        self.pos = [CHUNKSIZE / 2, CHUNKSIZE / 2]
        self.vectors = []

    def update(self):
        mult = 1 / (sum(fpsArr) / len(fpsArr))
        if pg.key.get_pressed()[pg.K_a]:
            self.vel[0] -= 40 * mult
        if pg.key.get_pressed()[pg.K_d]:
            self.vel[0] += 40 * mult
        if pg.key.get_pressed()[pg.K_SPACE] and [0, 1] in self.vectors:
            player.vel[1] -= 50
            player.pos[1] -= .05
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
    NOISE_TESTING_MODE = False
    CHUNKLOAD_RADIUS = 2
    CHUNKSIZE = 128
    SCALING = 4

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
    N = Noise()
    world = World()
    if NOISE_TESTING_MODE:
        thread = Thread(target=world.noise_display)
    else:
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
                if not thread.is_alive() and k == pg.K_BACKQUOTE and NOISE_TESTING_MODE:
                    s = input("s:")
                    N.SCALE = N.SCALE if s == "" else int(s)
                    o = input("o:")
                    N.OCTAVES = N.OCTAVES if o == "" else int(o)
                    p = input("p:")
                    N.PERSISTENCE = N.PERSISTENCE if p == "" else float(p)
                    f = input("f:")
                    N.FRACTAL_RATIO = N.FRACTAL_RATIO if f == "" else float(f)
                    b = input("b:")
                    N.SIGMOID_B = N.SIGMOID_B if b == "" else int(b)
                    so = input("so:")
                    N.SIGMOID_OFFSET = N.SIGMOID_OFFSET if so == "" else float(so)
                    if N.AVERAGE:
                        r = input("r:")
                        N.AVG_RADIUS = N.AVG_RADIUS if r == "" else int(r)
                        c = input("c:")
                        N.AVG_CUTOFF = N.AVG_CUTOFF if c == "" else int(c)
                        e = input("e:")
                        N.AVG_EFFECT = N.AVG_EFFECT if e == "" else float(e)
                    thread = Thread(target=world.noise_display)
                    thread.start()
                    print(N.SCALE, N.OCTAVES, N.PERSISTENCE, N.FRACTAL_RATIO, N.SEED, N.SIGMOID_B, N.SIGMOID_OFFSET,
                          N.AVERAGE, N.AVG_RADIUS, N.AVG_CUTOFF, N.AVG_EFFECT)
        if not NOISE_TESTING_MODE:
            initial_load = initial_load or world.loading_check()
            SURF.fill((0, 0, 0))
            if initial_load:
                if dt > 5:
                    world.chunks_loadingupdate()
                    dt = 0
                for c in world.chunks.values():
                    c.draw()
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
