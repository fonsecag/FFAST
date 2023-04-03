def loadData(env):pass

def loadUI(UIHandler, env):
    if True:
        return
    from UI.Loupe import VisualElement
    from vispy import scene

    class AtomsElement(VisualElement):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)


        def onDatasetInit(self):
            self.atoms = scene.visuals.Markers(
            pos=None,
            face_color=None,
            size=1,
            spherical=True,
            scaling=True,
            antialias=0,
            # edge_width=0.0015,
            edge_width=0,
            light_color=(1 - l, 1 - l, 1 - l),
            light_ambient=l,
            parent=view.scene,
        )