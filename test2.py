import sys
import numpy as np
from vispy import app, scene
from PySide6.QtWidgets import QApplication

from vispy.visuals.mesh import MeshVisual
import numpy as np
from numpy.linalg import norm
from vispy.util.transforms import rotate
from vispy.color import ColorArray
from vispy.scene.visuals import create_visual_node

import collections

class TubeVisual(MeshVisual):
    
    def __init__(self, points, radius=1.0,
                 closed=False,
                 color='grey',
                 tube_points=10,
                 shading='smooth',
                 vertex_colors=None,
                 face_colors=None,
                 mode='triangles'):

        # make sure we are working with floats
        points = np.array(points).astype(float)
        print(f'Points: {points.shape}')

        tangents, normals, binormals = _frenet_frames(points, closed)

        segments = len(points) - 1

        # if single radius, convert to list of radii
        if not isinstance(radius, collections.abc.Iterable):
            radius = [radius] * len(points)
        elif len(radius) != len(points):
            raise ValueError('Length of radii list must match points.')

        # get the positions of each vertex
        grid = np.zeros((len(points), tube_points, 3))
        for i in range(len(points)):
            pos = points[i]
            normal = normals[i]
            binormal = binormals[i]
            r = radius[i]

            # Add a vertex for each point on the circle
            v = np.arange(tube_points,
                          dtype=np.float32) / tube_points * 2 * np.pi
            cx = -1. * r * np.cos(v) # *(1 + np.random.random(tube_points)*0.1)
            cy = r * np.sin(v) # *(1 + np.random.random(tube_points)*0.1)
            grid[i] = (pos + cx[:, np.newaxis]*normal +
                       cy[:, np.newaxis]*binormal)


        # construct the mesh
        indices = []
        for i in range(0,segments,2):
            for j in range(tube_points):
                ip = (i+1) % segments if closed else i+1
                jp = (j+1) % tube_points

                index_a = i*tube_points + j
                index_b = ip*tube_points + j
                index_c = ip*tube_points + jp
                index_d = i*tube_points + jp

                indices.append([index_a, index_b, index_d])
                indices.append([index_b, index_c, index_d])

        vertices = grid.reshape(grid.shape[0]*grid.shape[1], 3)

        color = ColorArray(color)
        if vertex_colors is None:
            point_colors = np.resize(color.rgba,
                                     (len(points), 4))
            vertex_colors = np.repeat(point_colors, tube_points, axis=0)

        self.indices = np.array(indices, dtype=np.uint32)
        self.vertices = vertices

        MeshVisual.__init__(self, vertices, self.indices,
                            vertex_colors=vertex_colors,
                            face_colors=face_colors,
                            shading=shading,
                            mode=mode)

    def set_new_points_test(self, points):
        
        self._meshdata.set_vertices(self.vertices, reset_normals = False)
        self.mesh_data_changed()

    def set_new_points(self, points, radius=1.0,
                 closed=False,
                 color='grey',
                 tube_points=10,
                 shading='smooth',
                 vertex_colors=None,
                 face_colors=None,
                 mode='triangles'):

        # make sure we are working with floats
        points = np.array(points).astype(float)
        print(f'Points: {points.shape}')

        tangents, normals, binormals = _frenet_frames(points, closed)

        segments = len(points) - 1

        # if single radius, convert to list of radii
        if not isinstance(radius, collections.abc.Iterable):
            radius = [radius] * len(points)
        elif len(radius) != len(points):
            raise ValueError('Length of radii list must match points.')

        # get the positions of each vertex
        grid = np.zeros((len(points), tube_points, 3))
        for i in range(len(points)):
            pos = points[i]
            normal = normals[i]
            binormal = binormals[i]
            r = radius[i]

            # Add a vertex for each point on the circle
            v = np.arange(tube_points,
                          dtype=np.float32) / tube_points * 2 * np.pi
            cx = -1. * r * np.cos(v) # *(1 + np.random.random(tube_points)*0.1)
            cy = r * np.sin(v) # *(1 + np.random.random(tube_points)*0.1)
            grid[i] = (pos + cx[:, np.newaxis]*normal +
                       cy[:, np.newaxis]*binormal)

        vertices = grid.reshape(grid.shape[0]*grid.shape[1], 3)

        color = ColorArray(color)
        if vertex_colors is None:
            point_colors = np.resize(color.rgba,
                                     (len(points), 4))
            vertex_colors = np.repeat(point_colors, tube_points, axis=0)

        # self.set_data(vertices, self.indices,
        #                     vertex_colors=vertex_colors,
        #                     face_colors=face_colors)

        self._meshdata.set_vertices(vertices)
        self.mesh_data_changed()


Tube = create_visual_node(TubeVisual)

def _frenet_frames(points, closed):
    """Calculates and returns the tangents, normals and binormals for
    the tube.
    """
    tangents = np.zeros((len(points), 3))
    normals = np.zeros((len(points), 3))

    epsilon = 0.0001

    # Compute tangent vectors for each segment
    tangents = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
    if not closed:
        tangents[0] = points[1] - points[0]
        tangents[-1] = points[-1] - points[-2]
    mags = np.sqrt(np.sum(tangents * tangents, axis=1))
    tangents /= mags[:, np.newaxis]

    # Get initial normal and binormal
    t = np.abs(tangents[0])

    smallest = np.argmin(t)
    normal = np.zeros(3)
    normal[smallest] = 1.

    vec = np.cross(tangents[0], normal)

    normals[0] = np.cross(tangents[0], vec)

    # Compute normal and binormal vectors along the path
    for i in range(1, len(points)):
        normals[i] = normals[i-1]

        vec = np.cross(tangents[i-1], tangents[i])
        if norm(vec) > epsilon:
            vec /= norm(vec)
            theta = np.arccos(np.clip(tangents[i-1].dot(tangents[i]), -1, 1))
            normals[i] = rotate(-np.degrees(theta),
                                vec)[:3, :3].dot(normals[i])

    if closed:
        theta = np.arccos(np.clip(normals[0].dot(normals[-1]), -1, 1))
        theta /= len(points) - 1

        if tangents[0].dot(np.cross(normals[0], normals[-1])) > 0:
            theta *= -1.

        for i in range(1, len(points)):
            normals[i] = rotate(-np.degrees(theta*i),
                                tangents[i])[:3, :3].dot(normals[i])

    binormals = np.cross(tangents, normals)

    return tangents, normals, binormals

class TubeVisualizer:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.canvas = scene.SceneCanvas(keys='interactive', bgcolor='white', show=True)
        self.view = self.canvas.central_widget.add_view()

        # Prepare the tube data
        n_points = 500
        t = np.linspace(0, 2 * np.pi, n_points)
        x = np.cos(t)
        y = np.sin(t)
        z = np.linspace(-1, 1, n_points)

        # Create a tube
        self.tube_points = np.ones((n_points, 3))*np.arange(n_points).reshape(-1,1)
        self.tube_points[:,1:] = 0
        tube_points = self.tube_points

        # tube_points = np.array([
        #     [0,0,0], [0,1,0], [1,1,0], [1,0,0]
        # ]) * 10

        self.tube = Tube(tube_points, shading='smooth', tube_points=10, parent=self.view.scene)

        # Set up camera and view settings
        self.view.camera = 'arcball'
        self.view.camera.fov = 45
        self.view.camera.distance = 3
        self.view.camera.elevation = 30
        self.view.camera.azimuth = 30

    def update(self, ev):
        N = self.tube_points.shape[0]
        wave = np.sin(np.linspace(0, 2*np.pi, N)+ev.elapsed*2)

        tube_points = np.copy(self.tube_points)
        tube_points[:,1] = wave
        tube_points += np.random.random(tube_points.shape)*0.1

        self.tube.set_new_points(tube_points)


    def run(self):

        timer = app.Timer()
        timer.connect(self.update)
        timer.start(1/144)

        sys.exit(self.app.exec_())

if __name__ == '__main__':
    visualizer = TubeVisualizer()
    visualizer.run()
