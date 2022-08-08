from config.atoms import atomColors


class AtomColoringModeBase:
    def __init__(self, loupe):
        self.loupe = loupe

    def onGeometryUpdate(self):
        pass


class AtomicColoring(AtomColoringModeBase):
    def __init__(self, loupe):
        super().__init__(loupe)
        self.atomColors = None

    def onGeometryUpdate(self):
        z = self.loupe.dataset.getElements()
        self.atomColors = atomColors[z]

    def getColors(self):
        return self.atomColors


class ForceErrorColoring(AtomColoringModeBase):
    def __init__(self, loupe):
        super().__init__(loupe)
        self.atomColors = None

    def onGeometryUpdate(self):
        dataset = self.loupe.dataset
        model = self.loupe.colorTabModelCB.currentKey()
        if len(model) == 0:
            return
        else:
            model = model[0]

        if model is None:
            return

        env = self.loupe.handler.env

        err = env.getData("forcesError", dataset=dataset, model=model)
        if err is None:
            self.atomColors = None
            return

        print(err.get().shape)

    def getColors(self):
        dataset = self.loupe.dataset
