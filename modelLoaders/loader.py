import os
from events import EventClass
from Utils.misc import removeExtension


def loadModel(env, path):
    """
    Entry function for loading any model. This function simply decides which
    loader class should be used to load a model given a path, then returns
    a loaded object according.

    Args:
        path (str): path to the model
        fromCache (bool, optional): Flag controlling whether to load a dummy
            model. Used e.g. when the cache contains information on a model
            whose path is unknown or no longer exists. Defaults to False.

    Returns:
        ModelLoader: ModelLoader object for given path
    """
    model = None

    from .sGDML import sGDMLModelLoader
    from .SchNet import SchNetModelLoader

    if not os.path.exists(path):
        logger.error(f"Tried to load model, but path `{path}` not found")
        return None

    if path.endswith(".npz"):
        model = sGDMLModelLoader(env, path)
    elif "." not in path:
        model = SchNetModelLoader(env, path)
    else:
        model = None

    if model is not None:
        model.initialise()

    return model


class ModelLoader(EventClass):
    """
    Base class for any model. Contains all model-agnostic methods such as
    setting the display name and other parameters.

    Every model-dependent method, e.g. loading the model, predicting energies
    or forces, etc... are instead found in the specific ModelLoader subclasses.
    """

    def __init__(self, env, path):

        super().__init__()
        self.env = env

        self.path = path

    color = (0, 0, 0, 255)
    key = -1  # will be assigned by environment
    fingerprint = None
    loadeeType = "model"
    loaded = False
    isGhost = False
    singlePredict = False

    def setName(self, name):
        if name == "":
            return self.setName(self.name)
        self.name = name
        if self.loaded:
            self.eventPush("MODEL_NAME_CHANGED", self.fingerprint)

    def getDisplayName(self):
        return self.name

    def getName(self):
        return self.name

    def initialise(self):
        self.fingerprint = self.getFingerprint()

        name = removeExtension(os.path.basename(self.path))
        self.setName(name)
