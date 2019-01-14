from floppy.node import Node, abstractNode, Input, Output, Tag
from math import sin, cos, pi


def norm(v: list):
    d = (v[0]**2 + v[1]**2 + v[2]**2)**.5
    return [v[0]/d, v[1]/d, v[2]/d]


@abstractNode
class MathNode(Node):
    Tag('Math')


class Add(MathNode):
    Input('F1', float)
    Input('F2', float)
    Output('Sum', float)

    def run(self):
        self.o_Sum = self.i_F1.value + self.i_F2.value



@abstractNode
class VectorNode(MathNode):
    Tag('Vector')


class CreateVector(MathNode):
    Input('X', float)
    Input('Y', float)
    Input('Z', float)
    Output('V', float, list=True)
    def run(self):
        self.o_V = (self.i_X.value, self.i_Y.value, self.i_Z.value)


class CrossProduct(VectorNode):
    Input('Vector1', float, list=True)
    Input('Vector2', float, list=True)
    Output('XProduct', float, list=True)

    def run(self):
        super(CrossProduct, self).run()
        v1 = self.i_Vector1.value
        v2 = self.i_Vector2.value
        self.o_XProduct = (v1[1]*v2[2]-v1[2]*v2[1], v1[2]*v2[0]-v1[0]*v2[2], v1[0]*v2[1]-v1[1]*v2[0])


class DotProduct(VectorNode):
    """
    Compute Dot product of two input Vectors.
    """
    Input('Vector1', float, list=True)
    Input('Vector2', float, list=True)
    Output('DotProduct', float, list=False)

    def run(self):
        super(DotProduct, self).run()
        v1 = self.i_Vector1.value
        v2 = self.i_Vector2.value
        self.o_DotProduct = (v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2])


class Distance(VectorNode):
    Input('Position1', float, list=True)
    Input('Position2', float, list=True)
    Output('Distance', float, )

    def run(self):
        super(Distance, self).run()
        v1 = self.i_Position1.value
        v2 = self.i_Position2.value
        d = (v1[0]-v2[0])**2 + (v1[1]-v2[1])**2 + (v1[2]-v2[2])**2
        self._Distance = d**.5


class Difference(VectorNode):
    Input('Vector1', float, list=True)
    Input('Vector2', float, list=True)
    Output('Difference', float, list=True)

    def run(self):
        super(Difference, self).run()
        v1 = self._Position1
        v2 = self._Position2
        self._Difference((v1[0]-v2[0]), (v1[1]-v2[1]), (v1[2]-v2[2]))


class VectorSum(VectorNode):
    Input('Vector1', float, list=True)
    Input('Vector2', float, list=True)
    Output('Sum', float, list=True)

    def run(self):
        super(VectorSum, self).run()
        v1 = self.i_Vector1.value
        v2 = self.i_Vector2.value
        self.o_Sum = ((v1[0]+v2[0]), (v1[1]+v2[1]), (v1[2]+v2[2]))


class Normalize(VectorNode):
    Input('Vector', float, list=True)
    Output('NVector', float, list=True)

    def run(self):
        super(Normalize, self).run()
        # v = self._Vector
        # d = (v[0]**2 + v[1]**2 + v[2]**2)**.5
        # self._NVector((v[0]/d, v[1]/d, v[2]/d))
        self.o_NVector = norm(self.i_Vector.value)


class RotateAbout(VectorNode):
    Input('Point', float, list=True)
    Input('PointOnAxis', float, list=True)
    Input('AxisDirection', float, list=True)
    Input('Degree', float)
    Output('RotatedPoint', float, list=True)

    def run(self):
        super(RotateAbout, self).run()

        point = self.i_Point.value
        angle = self.i_Degree.value
        axisDirection = self.i_AxisDirection.value
        axisOrigin = self.i_PointOnAxis.value

        t = angle * (pi/180)
        x, y, z = point[0], point[1], point[2]
        a, b, c = axisOrigin[0], axisOrigin[1], axisOrigin[2]
        axisDirection /= norm(axisDirection)
        u, v, w = axisDirection[0], axisDirection[1], axisDirection[2]
        xx = (a*(v**2+w**2)-u*(b*v+c*w-u*x-v*y-w*z)) * (1-cos(t)) + x*cos(t) + (-1*c*v+b*w-w*y+v*z) * sin(t)
        yy = (b*(u**2+w**2)-v*(a*u+c*w-u*x-v*y-w*z)) * (1-cos(t)) + y*cos(t) + ( 1*c*u-a*w+w*x-u*z) * sin(t)
        zz = (c*(u**2+v**2)-w*(a*u+b*v-u*x-v*y-w*z)) * (1-cos(t)) + z*cos(t) + (-1*b*u+a*v-v*x+u*y) * sin(t)
        self.o_RotatedPoint = [xx, yy, zz]
