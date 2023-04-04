import numpy as np 
from UI.Loupe import VisualElement

def loadLoupe(UI, loupe):
    from vispy import scene
    
    class RandomOrbs(VisualElement):
        def __init__(self, *args,  parent = None, **kwargs):
            scatter = scene.visuals.Markers(scaling=True, spherical=True, parent = parent)
            super().__init__(*args, **kwargs, element = scatter)

            N = 100000
            pos = np.random.normal(size=(N, 3), scale=0.2)
            # one could stop here for the data generation, the rest is just to make the
            # data look more interesting. Copied over from magnify.py
            centers = np.random.normal(size=(50, 3))
            indexes = np.random.normal(size=N, loc=centers.shape[0] / 2,
                                    scale=centers.shape[0] / 3)
            indexes = np.clip(indexes, 0, centers.shape[0] - 1).astype(int)

            scales = 10**(np.linspace(-2, 0.5, centers.shape[0]))[indexes][:, np.newaxis]
            pos *= scales
            pos += centers[indexes]
            
            self.pos = pos
            self.colors = np.random.random((len(self.pos),3))

            
        def onNewGeometry(self):
            dc = np.random.normal(0, 0.05, self.colors.shape)
            self.colors = np.clip(self.colors + dc, 0, 1)
            self.pos = self.pos + np.random.normal(0, 0.0005, self.pos.shape)
            self.element.set_data(self.pos, face_color = self.colors, size = 0.02, edge_width = 0)


    loupe.addVisualElement(RandomOrbs)


def setTestData(self):
    pos = np.random.normal(size=(100000, 3), scale=0.2)
    # one could stop here for the data generation, the rest is just to make the
    # data look more interesting. Copied over from magnify.py
    centers = np.random.normal(size=(50, 3))
    indexes = np.random.normal(size=100000, loc=centers.shape[0] / 2,
                            scale=centers.shape[0] / 3)
    indexes = np.clip(indexes, 0, centers.shape[0] - 1).astype(int)

    scales = 10**(np.linspace(-2, 0.5, centers.shape[0]))[indexes][:, np.newaxis]
    pos *= scales
    pos += centers[indexes]
    colors = np.random.random((len(pos),4))

    scatter = scene.visuals.Markers(scaling=True, spherical=True, parent=self.view.scene)
    colors = np.random.random((len(pos),4))
    scatter.set_data(pos, edge_width=0.002, face_color=colors, size=0.02) 
