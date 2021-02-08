import math, random, numpy

#### GENERATION PARAMS ####
#CAVES: 200 8 .55 1.7 20 .06 40 90 1
class Noise:
    def __init__(self):
        self.SCALE = 100
        self.OCTAVES = 8
        self.PERSISTENCE = .55
        self.FRACTAL_RATIO = 1.7
        self.SEED = 34575334

        self.SIGMOID_B = 20
        self.SIGMOID_OFFSET = 0.06

        self.AVERAGE = True
        self.AVG_RADIUS = 20
        self.AVG_CUTOFF = 30
        self.AVG_EFFECT = 1

        self.point_cache = {}

    def worley(self, tp):
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

    def layered_worley(self, x, y):
        b = 1
        t = 0
        for i in range(self.OCTAVES):
            offset = self.SEED * (i + 1)
            t += self.worley((x * numpy.power(self.FRACTAL_RATIO, i) + offset, y * numpy.power(self.FRACTAL_RATIO, i) + offset)) * numpy.power(self.PERSISTENCE, i)
            b += numpy.power(self.PERSISTENCE, i)
        return t / b

    def set_pixel(self, x, y, arr):
        a = self.sigmoid(self.layered_worley(x / self.SCALE, y / self.SCALE) + self.SIGMOID_OFFSET) * 255
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

    def average_cutoff(self, center, source):
        if self.AVERAGE:
            arr = numpy.zeros((self.AVG_RADIUS * 2, self.AVG_RADIUS * 2))
            for x in range(self.AVG_RADIUS * 2):
                for y in range(self.AVG_RADIUS * 2):
                    arr[x, y] = source[x + center[0] - self.AVG_RADIUS, y + center[1] - self.AVG_RADIUS]
            t = sum(arr.flatten())
            div = (self.AVG_RADIUS ** 2) * 4
            if source[center[0], center[1], 0] >= ((t / div) - self.AVG_CUTOFF) * self.AVG_EFFECT + self.AVG_CUTOFF:
                return 255
            else:
                return 0
        else:
            return 255 if source[center[0], center[1], 0] > self.AVG_CUTOFF else 0

    def thread_avg(self, y, arr, W):
        arr2 = numpy.zeros((W, 1, 3))
        for x in range(W):
            arr2[x, 0, 0:3] = [self.average_cutoff((x, y), arr)] * 3
        return arr2, y

