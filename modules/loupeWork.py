from UI.loupeProperties import CanvasProperty
from client.dataWatcher import DataWatcher
from client.dataType import DataType
import numpy as np
from config.userConfig import getConfig
from scipy.optimize import minimize
from sklearn.neighbors import KDTree


DEPENDENCIES = ["loupeAtoms", "loupeForceError"]

# NOT USED ATM, TESTING


class WorkColorProperty(CanvasProperty):

    key = "workColor"

    def __init__(self, *args, **kwargs):
        from vispy.color import Colormap

        super().__init__(*args, **kwargs)

        self.colorMap = Colormap(
            [
                (0.1, 0.1, 0.9),
                (0.1, 0.9, 0.1),
                (0.9, 0.9, 0.1),
                (0.5, 0.1, 0.1),
                (0.9, 0.1, 0.1),
            ]
        )

    def onDatasetInit(self):
        # UPDATE THE DATAWATCHER'S DEPENDENCIES
        dw = self.canvas.loupe.loupeWorkDataWatcher
        dw.setDatasetDependencies(self.canvas.dataset.fingerprint)
        self.clear()
        self.manualUpdate()

    def getColors(self, r):
        return self.colorMap[r]

    def generate(self):
        dataset = self.canvas.dataset
        env = self.canvas.loupe.env
        setting = self.canvas.settings.get("atomColorType")

        data = env.getData("trajectoryWork", model=None, dataset=dataset)
        if not data:
            return

        if setting == "Work":
            x = data.get("atomicWork")
        elif setting == "Local Work":
            x = data.get("atomicLocalWork")
        else:
            x = data.get("atomicLocalWork") - data.get("atomicWork")

        x -= np.min(x)
        x /= np.max(x)

        colors = self.getColors(x)

        self.set(colors=colors)

    def manualUpdate(self):
        # gets called manually through an action when Coloring gets changed
        # or when the data loads

        setting = self.canvas.settings.get("atomColorType")
        atomsElement = self.canvas.elements["AtomsElement"]

        if (
            setting == "Work"
            or setting == "Local Work"
            or setting == "Work diff."
        ):
            atomsElement.colorProperty = self
        else:
            cp = atomsElement.colorProperty
            # remove cp if it's one of the force ones
            if cp is self:
                atomsElement.colorProperty = None

        self.clear()
        self.canvas.onNewGeometry()


def translation(shift, B):

    return B + shift


def rotation(angles, R0, B):

    phi_x, phi_y, phi_z = angles

    R_x = np.array(
        [
            [1, 0, 0],
            [0, np.cos(phi_x), -np.sin(phi_x)],
            [0, np.sin(phi_x), np.cos(phi_x)],
        ]
    ).squeeze()
    R_y = np.array(
        [
            [np.cos(phi_y), 0, np.sin(phi_y)],
            [0, 1, 0],
            [-np.sin(phi_y), 0, np.cos(phi_y)],
        ]
    ).squeeze()
    R_z = np.array(
        [
            [np.cos(phi_z), -np.sin(phi_z), 0],
            [np.sin(phi_z), np.cos(phi_z), 0],
            [0, 0, 1],
        ]
    ).squeeze()

    R = np.dot(R_x, np.dot(R_y, R_z))

    return translation(R0, np.einsum("ij, nj -> ni", R, translation(-R0, B)))


def displacement_field(dR):

    func = lambda par, x: np.linalg.norm(
        rotation(par[0:3], par[3:6], translation(par[6:9], x))
    )

    x0 = np.zeros(9)

    res = minimize(func, x0, dR).x
    angles, rotation_center, total_displacement = res[0:3], res[3:6], res[6:9]

    # print('angles', angles)
    # print('rotation_center', rotation_center)
    # print('total_displacement', total_displacement)

    return rotation(
        angles, rotation_center, translation(total_displacement, dR)
    )


def work(R, F):
    # rewrite as dot product axis 1
    return np.einsum("...i, ...i -> ...", R, F)


def nearest_neighbors(R, cutoff=1.5):

    tree = KDTree(R, leaf_size=2)
    ind = tree.query_radius(R, r=cutoff)

    natoms = R.shape[0]
    adj = np.zeros((natoms, natoms))
    for i in range(natoms):
        adj[i, ind[i]] = 1

    return adj


def loadData(env):
    if True:
        return

    class TrajectoryWork(DataType):
        modelDependent = False
        datasetDependent = True
        key = "trajectoryWork"
        dependencies = []
        iterable = False
        atomFilterable = True

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            R, F = dataset.getCoordinates(), dataset.getForces()
            nconf, natoms, _ = R.shape

            # calculate adjacency matrix
            min_freq = 0.8
            adj = np.zeros((natoms, natoms))
            for n in range(nconf):
                adj += nearest_neighbors(R[n])
            adj /= nconf
            adj[adj < min_freq] = 0
            adj[adj >= min_freq] = 1

            A = np.zeros(natoms)  # global
            B = np.zeros(natoms)  # local

            for n in range(1, nconf):
                r = displacement_field(R[n] - R[n - 1])
                f = (F[n] + F[n - 1]) / 2
                A += np.abs(work(r, f))

                for a in range(natoms):
                    r1 = R[n][adj[a] == 1]
                    r2 = R[n - 1][adj[a] == 1]
                    idx = np.where(np.arange(natoms)[adj[a] == 1] == a)[0]
                    r = displacement_field(r1 - r2)[idx]
                    f1 = F[n, a]
                    f2 = F[n - 1, a]
                    f = (f1 + f2) / 2
                    B[a] += np.abs(work(r, f))

                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=nconf,
                    prog=n,
                    message="Iterating traj",
                    quiet=True,
                )

            A /= nconf
            B /= nconf
            de = self.newDataEntity(atomicWork=A, atomicLocalWork=B)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    env.registerDataType(TrajectoryWork)


def loadLoupe(UIHandler, loupe):
    if True:
        return

    from UI.Plots import DataloaderButton

    pane = loupe.getSettingsPane("ATOMS")
    comboBox = pane.settingsWidgets.get("Coloring")
    comboBox.addItems(["Work", "Local Work", "Work diff."])

    loupe.addCanvasProperty(WorkColorProperty)
    # loupe.addCanvasProperty(TotDisplacementColorProperty)
    # loupe.addCanvasProperty(MeanDisplacementColorProperty)

    ## ADDING DATAWATCHER
    ## Dataset dependency set by WorkColorProperty
    dw = DataWatcher(loupe.env)
    loupe.loupeWorkDataWatcher = dw
    dw.setDataDependencies("trajectoryWork")

    ## ADD BUTTONS AND SHIT
    # CONTAINER
    container = pane.addSetting(
        "Container", "Work Container", layout="horizontal", insertIndex=1,
    )
    container.setHideCondition(
        lambda: not (
            settings.get("atomColorType") == "Work"
            or settings.get("atomColorType") == "Local Work"
            or settings.get("atomColorType") == "Work diff."
        )
    )

    btn = DataloaderButton(UIHandler, dw)
    container.layout.addStretch()
    container.layout.addWidget(btn)
    btn.setFixedWidth(80)

    # callbacks
    def updateWorkColor():
        prop = loupe.canvas.props["workColor"]
        prop.manualUpdate()

    settings = loupe.settings
    settings.addParameterActions("atomColorType", updateWorkColor)

    dw.addCallback(updateWorkColor)
