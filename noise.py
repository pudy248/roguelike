import math, random, numpy

#### GENERATION PARAMS ####
#CAVES: 50 5 .53 1.7 12 .07 20 110 .98
class Noise:
    def __init__(self):
        self.SCALE = 200
        self.OCTAVES = 8
        self.PERSISTENCE = .55
        self.FRACTAL_RATIO = 1.7
        self.SEED = 3463135

        self.SIGMOID_B = 20
        self.SIGMOID_OFFSET = 0.06

        self.AVERAGE = True
        self.AVG_RADIUS = 40
        self.AVG_CUTOFF = 90
        self.AVG_EFFECT = 1

        self.point_cache = {}
        self.average_groups = {}
        self.average_group_size = 10

    def perlin(self, tp):
        x1 = int(tp[0])
        y1 = int(tp[1])
        x2 = tp[0] - x1
        y2 = tp[1] - y1
        points = []
        for i in range(3):
            for j in range(3):
                if not ((x1 + i - 1), (y1 + j - 1)) in self.point_cache.keys():
                    random.seed((x1 + i - 1) * (y1 + j - 1) + self.SEED)
                    x3 = random.random()
                    y3 = random.random()
                    self.point_cache.update({((x1 + i - 1), (y1 + j - 1)): (x3, y3)})
                points.append((self.point_cache[((x1 + i - 1), (y1 + j - 1))][0] + i - 1, self.point_cache[((x1 + i - 1), (y1 + j - 1))][1] + j - 1))
        distance = []
        for n in points:
            distance.append(math.hypot(x2 - n[0], y2 - n[1]))
        return min(distance)

    def layered_perlin(self, x, y):
        b = 1
        t = 0
        for i in range(self.OCTAVES):
            offset = self.SEED * (i + 1)
            t += self.perlin((x * numpy.power(self.FRACTAL_RATIO, i) + offset, y * numpy.power(self.FRACTAL_RATIO, i) + offset)) * numpy.power(self.PERSISTENCE, i)
            b += numpy.power(self.PERSISTENCE, i)
        return t / b

    def set_pixel(self, x, y, arr):
        a = self.sigmoid(self.layered_perlin(x / self.SCALE, y / self.SCALE) + self.SIGMOID_OFFSET) * 255
        arr[x, y % 10, 0: 3] = [a] * 3

    def thread_f(self, y, W):
        arr = numpy.zeros((W, 10, 3))
        for y1 in range(10):
            for x in range(int(W)):
                self.set_pixel(x, y+y1, arr)
        return arr, y

    def sigmoid(self, x):
        # wolfram alpha came up with this equation i have no idea what a hyperbolic sine is but it works
        return .5 * (1 / numpy.sinh(self.SIGMOID_B / 4)) * (1 / numpy.cosh(.25 * (self.SIGMOID_B - (2 * self.SIGMOID_B * x)))) * numpy.sinh(self.SIGMOID_B * x / 2)

    def average_cutoff(self, center1, source):
        if self.AVERAGE:
            center = (int(center1[0] / self.average_group_size), int(center1[1] / self.average_group_size))
            radius = int(self.AVG_RADIUS / self.average_group_size)
            arr = numpy.zeros((radius * 2 + 1, radius * 2 + 1))
            startx = 0
            starty = 0
            endx = radius * 2 + 1
            endy = radius * 2 + 1
            if center[0] < radius:
                startx = radius - center[0]
            if center[1] < radius:
                starty = radius - center[1]
            if center[0] > source.shape[0] - radius - 1:
                endx = radius + (source.shape[0] - center[0])
            if center[1] > source.shape[1] - radius - 1:
                endy = radius + (source.shape[1] - center[1])
            for x in range(startx, endx):
                for y in range(starty, endy):
                    arr[x, y] = self.avg_square(x, y, source)
            t = sum(arr.flatten())
            div = sum(map(lambda m: 1 if m > 0 else 0, arr.flatten()))
            if source[center1[0], center1[1], 0] >= ((t / div) - self.AVG_CUTOFF) * self.AVG_EFFECT + self.AVG_CUTOFF:
                return 255
            else:
                return 0
        else:
            return 255 if source[center1[0], center1[1], 0] > self.AVG_CUTOFF else 0

    def avg_square(self, x, y, arr):
        if (x, y) not in self.average_groups.keys():
            sum = 0
            entries = 0
            for x1 in range(self.average_group_size):
                for y1 in range(self.average_group_size):
                    entries += 1
                    sum += arr[(x * self.average_group_size + x1), (y * self.average_group_size + y1), 0]
            self.average_groups.update({(x, y): sum /entries})
            return sum / entries
        else:
            return self.average_groups[(x, y)]

    def thread_avg(self, y, arr, W):
        arr2 = numpy.zeros((W, 1, 3))
        for x in range(W):
            arr2[x, 0, 0:3] = self.average_cutoff((x, y), arr)
        return arr2, y

