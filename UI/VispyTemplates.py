import numpy as np
from vispy import app, scene
from vispy.visuals.tube import _frenet_frames
from vispy.visuals.mesh import MeshVisual
from vispy.color import ColorArray
import collections
from vispy.scene.visuals import create_visual_node

class TubeVisual(MeshVisual):
    lastNumberOfPoints = None
    vertices = None
    indices = None

    def __init__(self, radius=1.0,
                 color=(0.7, 0.7, 0.7, 1),
                 tube_points=10,
                 shading='smooth',
                 mode='triangles'):

        self.tube_points = tube_points
        self.radius = radius
     
        MeshVisual.__init__(self, np.zeros((3, 3)), np.array([[0,1,2]]),
                            shading=shading, color = color,
                            mode=mode)


    def generate_new_indices(self, nPoints):
        
        if nPoints == self.lastNumberOfPoints:
            return
        
        self.lastNumberOfPoints = nPoints

        tube_points = self.tube_points
        segments = nPoints - 1

        # construct the mesh
        indices = []
        for i in range(0,segments,2):
            for j in range(tube_points):
                ip = (i+1)
                jp = (j+1) % tube_points

                index_a = i*tube_points + j
                index_b = ip*tube_points + j
                index_c = ip*tube_points + jp
                index_d = i*tube_points + jp

                indices.append([index_a, index_b, index_d])
                indices.append([index_b, index_c, index_d])


        self.indices = np.array(indices, dtype=np.uint32)

    def generate_new_vertices(self, points):

        tangents, normals, binormals = _frenet_frames(points, False)

        tube_points = self.tube_points
        radius = self.radius

        # get the positions of each vertex
        grid = np.zeros((len(points), tube_points, 3))
        for i in range(len(points)):
            pos = points[i]
            normal = normals[i]
            binormal = binormals[i]

            # Add a vertex for each point on the circle
            v = np.arange(tube_points,
                          dtype=np.float32) / tube_points * 2 * np.pi
            cx = -1. * radius * np.cos(v) # *(1 + np.random.random(tube_points)*0.1)
            cy = radius * np.sin(v) # *(1 + np.random.random(tube_points)*0.1)
            grid[i] = (pos + cx[:, np.newaxis]*normal +
                       cy[:, np.newaxis]*binormal)

        self.vertices = grid.reshape(grid.shape[0]*grid.shape[1], 3)

    def set_new_points(self, points):
        self.generate_new_vertices(points)
        self.generate_new_indices(len(points))
        self.set_data(self.vertices, self.indices)

Tube = create_visual_node(TubeVisual)
