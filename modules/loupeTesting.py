import numpy as np
from UI.Loupe import VisualElement


def loadLoupe(UI, loupe):

    if True:
        return

    from vispy import scene

    class RandomOrbs(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            scatter = scene.visuals.Markers(
                scaling=True, spherical=True, parent=parent
            )
            super().__init__(*args, **kwargs, element=scatter)

            N = 10000
            pos = np.random.normal(size=(N, 3), scale=0.2)
            # one could stop here for the data generation, the rest is just to make the
            # data look more interesting. Copied over from magnify.py
            centers = np.random.normal(size=(50, 3))
            indexes = np.random.normal(
                size=N, loc=centers.shape[0] / 2, scale=centers.shape[0] / 3
            )
            indexes = np.clip(indexes, 0, centers.shape[0] - 1).astype(int)

            scales = (
                10
                ** (np.linspace(-2, 0.5, centers.shape[0]))[indexes][
                    :, np.newaxis
                ]
            )
            pos *= scales
            pos += centers[indexes]

            self.pos = pos
            self.colors = np.random.random((len(self.pos), 3))
            self.sizes = np.random.random(len(self.pos)) * 0.02
            self.time = 0
            self.period = 20

        def onNewGeometry(self):
            self.time = self.canvas.index
            dc = np.random.normal(0, 0.05, self.colors.shape)
            self.colors = np.clip(self.colors + dc, 0, 1)
            self.pos = self.pos + np.random.normal(0, 0.0005, self.pos.shape)
            self.queueVisualRefresh()

        def draw(self):
            self.element.set_data(
                self.pos,
                face_color=self.colors,
                size=0.01 + self.sizes * np.cos(self.time / self.period),
                edge_width=0.001,
            )


    for i in range(1):
        loupe.addVisualElement(RandomOrbs)

