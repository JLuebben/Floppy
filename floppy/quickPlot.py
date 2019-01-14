"""
Dependency free module to create simple SVG graphics.
"""
BLACK = "rgb(0,0,0)"
WHITE = "rgb(255,255,255)"
BLUE = "rgb(0,0,255)"
RED = "rgb(255,0,0)"
GREEN = "rgb(0,255,0)"
YELLOW = "rgb(255,255,0)"
MAGENTA = "rgb(255,0,255)"
CYAN = "rgb(0,255,255)"
ORANGE = "rgb(255,160,0)"
C1 = "#00A8A8"
C2 = "#0F42B7"
C3 = "#FF7400"
C4 = "#FFAA00"
PLOTCOLORS = [C1, C2, C3, C4]


class SVG(object):
    def __init__(self, width, height, color=None):
        self.color = color
        self.width = width
        self.height = height
        self.elements = []
        self.frame = []

    def setWidth(self, width):
        self.width = width

    def addFrame(self, color=BLACK, width=2):
        self.frame = [
            SVGLine(self, 0, 0, 0, 1, color, width),
            SVGLine(self, 0, 1, 1, 1, color, width),
            SVGLine(self, 1, 1, 1, 0, color, width),
            SVGLine(self, 1, 0, 0, 0, color, width)]

    def removeFrame(self):
        for line in self.frame:
            self.elements.remove(line)
        self.frame = []

    def addElement(self, element):
        self.elements.append(element)

    def scaleElements(self):
        [element._scale(self.width, self.height) for element in self.elements]

    def __str__(self):
        self._pre()
        self.scaleElements()

        s = '<svg height="{height}", width="{width}", {style}>\n   '.format(width=self.width, height=self.height,
                                                                            style='style="stroke-width: 0px; background-color: {};"'.format(
                                                                                self.color) if self.color else '')
        s += '\n   '.join([str(element) for element in self.elements])
        s += '\n</svg>\n'
        return s

    def _pre(self):
        return ''


class SVGElement(object):
    def __init__(self):
        pass


class SVGLine(SVGElement):
    def __init__(self, document, startX, startY, endX, endY, color=BLACK, width=2, absoluteSize=False, id=None):
        super(SVGLine, self).__init__()
        self.id = id
        self.document = document
        self.document.addElement(self)
        self.x1 = startX
        self.x2 = endX
        self.y1 = 1 - startY
        self.y2 = 1 - endY
        self.color = color
        self.width = width
        self.xx1 = None
        self.yy1 = None
        self.xx2 = None
        self.yy2 = None
        self.absoluteSize = absoluteSize
        if absoluteSize:
            self.xx1 = self.x1
            self.yy1 = self.y1
            self.xx2 = self.x2
            self.yy2 = self.y2

    def _scale(self, sizeX, sizeY, offsetX=0, offsetY=0):
        if self.absoluteSize:
            return
        self.xx1 = sizeX * self.x1 + offsetX * sizeX
        self.yy1 = sizeY * self.y1 + offsetY * sizeY
        self.xx2 = sizeX * self.x2 + offsetX * sizeX
        self.yy2 = sizeY * self.y2 + offsetY * sizeY

    def __str__(self):
        if self.xx1 is None:
            raise AttributeError('No image size given.')
        return '<line {id} x1="{x1:5.0f}" y1="{y1:5.0f}" x2="{x2:5.0f}" y2="{y2:5.0f}" ' \
               'style="stroke:{color};stroke-width:{stroke}" />'.format(x1=self.xx1,
                                                                        y1=self.yy1,
                                                                        x2=self.xx2,
                                                                        y2=self.yy2,
                                                                        color=self.color,
                                                                        stroke=self.width,
                                                                        id='id="{}"'.format(self.id) if self.id else '')


class SVGText(SVGElement):
    def __init__(self, document, text, x, y, color=BLACK, size=20, absolutePos=False, id=None, rotate=None):
        super(SVGText, self).__init__()
        self.document = document
        self.document.addElement(self)
        self.text = text
        self.x = x
        self.y = 1 - y
        self.color = color
        self.size = size
        self.absolutePos = absolutePos
        self.id = id
        self.rotate = rotate
        if absolutePos:
            self.xx = self.x
            self.yy = self.y
        else:
            self.xx = None
            self.yy = None

    def _scale(self, sizeX, sizeY, offsetX=0, offsetY=0):
        if self.absolutePos:
            return
        self.xx = sizeX * self.x + offsetX * sizeX
        self.yy = sizeY * self.y + offsetY * sizeY

    def __str__(self):
        if self.xx is None:
            raise AttributeError('No image size given.')
        x = '{:5.0f}'.format(self.xx).lstrip()
        y = '{:5.0f}'.format(self.yy).lstrip()
        return '<text {id} x="{x}" y="{y}"' \
               'fill="{color}" {transform} {size}>{text}</text>'.format(x=x,
                                                                        y=y,
                                                                        color=self.color,
                                                                        id='id="{}"'.format(self.id) if self.id else '',
                                                                        text=self.text,
                                                                        transform='transform="rotate({},{},{})"'.format(
                                                                            self.rotate, x, y) if self.rotate else '',
                                                                        size='style="font-size:{}px"'.format(
                                                                            self.size) if self.size else '')


class LinePlot(SVG):
    def __init__(self, width, height, color = BLUE, rangeX=None, rangeY=None):
        super(LinePlot, self).__init__(width, height, color)
        self.minX = 0
        self.minY = 0
        self.maxX = 1
        self.maxY = 1
        self.X = []
        self.Y = []
        self.axes = []
        self.points = []
        self.setAxisMargins()
        self.addAxes()
        self.setTicks()

    def setAxisMargins(self, marginX=.06, marginY=.06):
        self.marginX = marginX
        self.marginY = marginY

    def setTicks(self, ticksX=2, ticksY=.2):
        self.ticksX = ticksX
        self.ticksY = ticksY

    def addAxes(self):
        self.axes = {
            SVGLine(self, self.marginX, self.marginY, 1 - self.marginX, self.marginY, width=4),
            SVGLine(self, self.marginX, self.marginY, self.marginX, 1 - self.marginY, width=4)}

    def scaleElements(self):
        inner = [element for element in self.elements if not element in self.axes and not element in self.frame]
        [element._scale(self.width - (self.width * 2 * self.marginX),
                        self.height - (self.height * 2 * self.marginY),
                        self.marginX, self.marginY) for
         element in inner]
        [element._scale(self.width, self.height) for element in self.frame]
        [element._scale(self.width, self.height) for element in self.axes]

    def addPoint(self, x=None, y=None):
        if not x and not y:
            raise ValueError('No Y values.')
        if not x:
            try:
                x = self.X[-1] + 1
            except IndexError:
                x = 0

        self.X.append(x)
        self.Y.append(y)

    def plot(self):
        for point in self.points:
            self.elements.remove(point)
        self.points = []
        self.minX = min(self.X)
        self.maxX = max(self.X)
        self.minY = min([min(y) for y in self.Y])
        self.maxY = max([max(y) for y in self.Y])
        self.rangeX = self.maxX - self.minX
        if not self.rangeX: self.rangeX = 1
        self.rangeY = self.maxY - self.minY
        if not self.rangeY: self.rangeY = 1
        prevX = self.X[0]
        prevYs = self.Y[0]
        for x, y in zip(self.X, self.Y):
            newYs = []
            for i, yy in enumerate(y):
                prevY = prevYs[i]
                x1 = (prevX - self.minX) / self.rangeX
                x2 = (x - self.minX) / self.rangeX
                y1 = (prevY - self.minY) / self.rangeY
                y2 = (yy - self.minY) / self.rangeY
                self.points.append(SVGLine(self, x1, y1, x2, y2, color=PLOTCOLORS[i]))
                newYs.append(yy)
            prevYs = newYs
            prevX = x
        tickX = self.ticksX + self.minX
        while tickX < self.maxX:
            x = (tickX - self.minX) / self.rangeX
            self.points.append(SVGLine(self, x, 0, x, 0.02, ))
            self.points.append(SVGText(self, str(tickX), x - .01, -.06, size=15))
            tickX += self.ticksX

        tickY = self.ticksY + self.minY
        while tickY < self.maxY:
            y = (tickY - self.minY) / self.rangeY
            self.points.append(SVGLine(self, 0, y, 0.02, y, ))
            self.points.append(SVGText(self, '{:4.2f}'.format(tickY), -0.003, y - 0.05, size=15, rotate=-90))
            tickY += self.ticksY

        self.points.append(SVGLine(self, 0.005, -.01, 0.02, 0.02, ))
        self.points.append(SVGText(self, str(self.minX), -.01, -.06, size=15))


from random import random

count = 1


def test(width):
    document = LinePlot(width, 320)
    document.addFrame()
    global count

    # line = SVGLine(document, 0, 0, 1, 1, color=C1)
    # line = SVGLine(document, 0.5, 1, 1, 0, color=C2)
    # line = SVGLine(document, 0, 1, 1, 0, color=C3)
    # line = SVGLine(document, 0, 1, .5, 0, color=C4)
    for _ in range(count):
        document.addPoint(x=_, y=(random(), random(), random(), random()))
    count += 1
    # document.addPoint(x=1, y=(.5, .1, .7, 0.5))
    # document.addPoint(x=2, y=(.6, .03, .5, 0.7))
    # document.addPoint(x=9, y=(.6, .2, .7, 0.5))

    document.plot()
    return document


if __name__ == '__main__':
    print(test(450))
