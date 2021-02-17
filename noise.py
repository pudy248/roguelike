import math, random, numpy

class Noise:
    def __init__(self):
        self.SCALE = 10
        self.OCTAVES = 7
        self.PERSISTENCE = .5
        self.FRACTAL_RATIO = 1.7
        self.SEED = int(random.random() * 1000000)

        self.SIGMOID_B = 4
        self.SIGMOID_OFFSET = 0.07

        self.AVERAGE = True
        self.AVG_RADIUS = 10
        self.AVG_CUTOFF = 80
        self.AVG_EFFECT = .98

        self.interp_scale = 6
        self.points = {}
        self.points_avg = {}

    def worley(self, tp):
        x1 = int(tp[0])
        y1 = int(tp[1])
        x2 = tp[0] - x1
        y2 = tp[1] - y1
        points = []
        for i in range(3):
            for j in range(3):
                random.seed((x1 + i - 1) * (y1 + j - 1) + self.SEED)
                x3 = random.random()
                y3 = random.random()
                points.append((x3 + i - 1, y3 + j - 1))
        distance = []
        for n in points:
            distance.append(math.hypot(x2 - n[0], y2 - n[1]))
        return min(distance)

    def sigmoid(self, x):
        if self.SIGMOID_B <= 1:
            return x
        else:
            return .5 * (1 / numpy.sinh(self.SIGMOID_B / 4)) * (1 / numpy.cosh(.25 * (self.SIGMOID_B - (2 * self.SIGMOID_B * x)))) * numpy.sinh(self.SIGMOID_B * x / 2)

    def layered_worley(self, xi, yi):
        if (xi, yi) not in self.points.keys():
            x = (xi / self.SCALE) / self.interp_scale
            y = (yi / self.SCALE) / self.interp_scale
            b = 1
            t = 0
            for i in range(self.OCTAVES):
                offset = self.SEED * (i + 1)
                t += self.worley((x * numpy.power(self.FRACTAL_RATIO, i) + offset,
                                  y * numpy.power(self.FRACTAL_RATIO, i) + offset)) * numpy.power(self.PERSISTENCE, i)
                b += numpy.power(self.PERSISTENCE, i)
            self.points.update({(xi, yi): self.sigmoid(t / b + self.SIGMOID_OFFSET) * 255})
        return self.points[(xi, yi)]

    def pixel_avg(self, xi, yi):
        if (xi, yi) not in self.points_avg.keys():
            if self.AVERAGE:
                arr = numpy.zeros((self.AVG_RADIUS * 2, self.AVG_RADIUS * 2))
                for x in range(self.AVG_RADIUS * 2):
                    for y in range(self.AVG_RADIUS * 2):
                        arr[x, y] = self.layered_worley(x + xi - self.AVG_RADIUS, y + yi - self.AVG_RADIUS)
                t = sum(arr.flatten())
                div = (self.AVG_RADIUS ** 2) * 4
                a = self.layered_worley(xi, yi) + (((t / div) - self.AVG_CUTOFF) * self.AVG_EFFECT)
            else:
                a = self.layered_worley(xi, yi)
            self.points_avg.update({(xi, yi): a})
        return self.points_avg[(xi, yi)]

    def interp_avg(self, x, y):
        xr = (x % self.interp_scale) / self.interp_scale
        yr = (y % self.interp_scale) / self.interp_scale

        p1 = self.pixel_avg(x - (x % self.interp_scale), y - (y % self.interp_scale))
        p2 = self.pixel_avg(x - (x % self.interp_scale) + self.interp_scale, y - (y % self.interp_scale))
        p3 = self.pixel_avg(x - (x % self.interp_scale), y - (y % self.interp_scale) + self.interp_scale)
        p4 = self.pixel_avg(x - (x % self.interp_scale) + self.interp_scale, y - (y % self.interp_scale) + self.interp_scale)

        return (p4 * xr * yr) + (p3 * (1 - xr) * yr) + (p2 * (1 - yr) * xr) + (p1 * (1 - xr) * (1 - yr))
