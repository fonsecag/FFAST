"""
CachedRemoteDataset — local wrapper for arrays transferred from a remote
ffast-server over the WebSocket RPC channel.

Lifecycle
---------
1. Server fires REMOTE_DATASET_META → client creates a proxy instance
   (``is_remote_proxy=True``, no arrays yet).  The proxy appears in the Loupe
   dataset ComboBox so the user can select it.

2. User selects the proxy in Loupe → env.taskFetchRemoteDataset(fingerprint)
   is triggered automatically.

3. Task calls session.request_subdataset_arrays(fingerprint), receives the
   arrays, and calls proxy.populate(arrays).

4. REMOTE_ARRAY_FETCH_DONE event fires → Loupe refreshes and renders at full
   interactivity (GPU picking works because real arrays are now in place).
"""
import logging

import numpy as np

from datasetLoaders.loader import DatasetLoader

logger = logging.getLogger("FFAST")


class CachedRemoteDataset(DatasetLoader):
    """Local dataset backed by arrays transferred from a remote server.

    When constructed without arrays (``arrays=None``) the object acts as a
    lightweight proxy: ``getN()`` and ``getNAtoms()`` work, but
    ``getCoordinates()`` returns zeros so Loupe can initialise without
    crashing.  Call ``populate(arrays)`` once the transfer completes to
    promote the proxy to a fully functional dataset.
    """

    isSubDataset = False         # no parent — env would crash expecting .parent
    isAtomFiltered = False
    frozen = False
    isVariable = False
    isGhost = False

    datasetName = "Remote Dataset"
    datasetType = "CachedRemoteDataset"
    datasetFileExtension = "*"
    saveFormats = [None]

    def __init__(self, fingerprint: str, name: str, n: int, arrays=None):
        """
        Parameters
        ----------
        fingerprint : str
            Server-side fingerprint used as the local key.
        name : str
            Human-readable label shown in the UI.
        n : int
            Number of configurations (known from REMOTE_DATASET_META before
            arrays arrive).
        arrays : dict | None
            If supplied, the dataset is immediately fully populated.
        """
        # DatasetLoader.__init__ increments the global colour counter and
        # assigns self.color — pass an empty path.
        super().__init__("")

        self.fingerprint = fingerprint
        self._name = name
        self._n = n

        # Uniform format
        self._R = None      # (N, natoms, 3) float64
        self._F = None      # (N, natoms, 3) float64 or None
        self._z = None      # (natoms,) int
        self._natoms = 0

        # Variable format (molecules of different sizes)
        self._R_flat = None     # (total_atoms, 3) float64
        self._F_flat = None     # (total_atoms, 3) float64 or None
        self._z_flat = None     # (total_atoms,) int
        self._offsets = None    # (N+1,) int — molecule start indices

        self._E = None          # (N,) float64 — energies (uniform + variable)

        self.loaded = True  # so setName fires OBJECT_NAME_CHANGED correctly
        self.setName(name)

        if arrays is not None:
            self._apply_arrays(arrays)

    # ── proxy state ──────────────────────────────────────────────────────────

    @property
    def is_remote_proxy(self) -> bool:
        """True while arrays have not yet been fetched from the server."""
        return self._R is None and self._R_flat is None

    def populate(self, arrays: dict) -> None:
        """Fill in the transferred arrays and update derived state.

        Called by env.taskFetchRemoteDataset once the transfer completes.
        """
        self._apply_arrays(arrays)
        logger.info(
            "CachedRemoteDataset %r populated: n=%d variable=%s",
            self.fingerprint, self._n, self.isVariable,
        )
        # Recompute bond sizes for uniform datasets where z is known
        if not self.isVariable and self._z is not None:
            from config.atoms import covalentBonds
            from config.userConfig import getConfig
            z = self._z
            self.bondSizes = covalentBonds[z][:, z] * getConfig(
                "loupeBondsLenience"
            )

    def _apply_arrays(self, arrays: dict) -> None:
        # Decode config count
        n_arr = arrays.get("n")
        if n_arr is not None:
            self._n = int(np.asarray(n_arr).flat[0])

        # Detect variable vs uniform from the "variable" flag sent by server
        var_flag = arrays.get("variable")
        is_variable = bool(
            var_flag is not None and int(np.asarray(var_flag).flat[0])
        )

        if is_variable:
            # Variable format: flat arrays + offsets
            self.isVariable = True
            offsets_raw = arrays.get("offsets")
            if offsets_raw is not None:
                self._offsets = np.asarray(offsets_raw, dtype=np.int64)

            R_flat = arrays.get("R_flat")
            if R_flat is not None:
                self._R_flat = np.asarray(R_flat, dtype=np.float64)

            F_flat = arrays.get("F_flat")
            self._F_flat = (
                np.asarray(F_flat, dtype=np.float64) if F_flat is not None else None
            )

            z_flat = arrays.get("z_flat")
            if z_flat is not None:
                self._z_flat = np.asarray(z_flat, dtype=np.int32)
        else:
            # Uniform format: (N, natoms, 3)
            R = arrays.get("R")
            if R is not None:
                self._R = np.asarray(R, dtype=np.float64)
                self._n = len(self._R)
                self._natoms = self._R.shape[1] if self._R.ndim == 3 else 0

            F = arrays.get("F")
            self._F = np.asarray(F, dtype=np.float64) if F is not None else None

            z_raw = arrays.get("z")
            if z_raw is not None:
                self._z = np.asarray(z_raw, dtype=np.int32)

        # Energies — shape (N,), same for uniform and variable
        E_raw = arrays.get("E")
        if E_raw is not None:
            self._E = np.asarray(E_raw, dtype=np.float64).reshape(-1)

    # ── DatasetLoader interface ───────────────────────────────────────────────

    def initialise(self):
        """Skip the normal fingerprint-from-data step; fingerprint is pre-set."""
        pass

    def setName(self, name):
        if name == "":
            return
        self.name = name
        if self.loaded:
            self.eventPush("OBJECT_NAME_CHANGED", self.fingerprint)

    def getName(self):
        return self.name

    def getDisplayName(self):
        return f"[Remote] {self.name}"

    def getN(self) -> int:
        return self._n

    def getNAtoms(self, index=None):
        if self.isVariable and self._offsets is not None:
            if index is None:
                return np.diff(self._offsets)
            return int(self._offsets[index + 1] - self._offsets[index])
        return self._natoms

    def getCoordinates(self, indices=None):
        if self.isVariable:
            if self._R_flat is None:
                # proxy: return zeros for first molecule
                return np.zeros((1, 3), dtype=np.float64)
            if indices is None:
                indices = np.arange(self._n)
            if not hasattr(indices, "__iter__"):
                # single molecule
                s, e = self._offsets[indices], self._offsets[indices + 1]
                return self._R_flat[s:e]
            # multiple molecules → list (same as VariableDatasetLoader)
            result = []
            for idx in indices:
                s, e = self._offsets[idx], self._offsets[idx + 1]
                result.append(self._R_flat[s:e])
            return result
        # Uniform
        if self._R is None:
            natoms = max(self._natoms, 1)
            shape = (self._n, natoms, 3) if indices is None else (1, natoms, 3)
            return np.zeros(shape, dtype=np.float64)
        if indices is None:
            return self._R
        return self._R[indices]

    def getForces(self, indices=None):
        if self.isVariable:
            if self._F_flat is None:
                return None
            if indices is None:
                indices = np.arange(self._n)
            if not hasattr(indices, "__iter__"):
                s, e = self._offsets[indices], self._offsets[indices + 1]
                return self._F_flat[s:e]
            result = []
            for idx in indices:
                s, e = self._offsets[idx], self._offsets[idx + 1]
                result.append(self._F_flat[s:e])
            return result
        if self._F is None:
            return None
        if indices is None:
            return self._F
        return self._F[indices]

    def getEnergies(self, indices=None):
        if self._E is None:
            return None
        if indices is None:
            return self._E
        return self._E[indices]

    def getElements(self, index=None):
        if self.isVariable:
            z = self._z_flat
            if z is None:
                return np.array([], dtype=np.int32)
            if index is None:
                return z
            s, e = self._offsets[index], self._offsets[index + 1]
            return z[s:e]
        if self._z is None:
            return np.array([], dtype=np.int32)
        return self._z

    def getAtomicNumbers(self):
        return self.getElements()

    def getChemicalFormula(self):
        if self.isVariable:
            z = self._z_flat
            if z is None:
                return "?"
            atom_counts = self.getNAtoms()
            if hasattr(atom_counts, "min"):
                return f"Variable ({atom_counts.min()}–{atom_counts.max()} atoms)"
            return "Variable"
        if self._z is None:
            return "?"
        return self.zToChemicalFormula(self._z)

    def getElementsName(self):
        from config.atoms import zIntToZStr
        z = self._z_flat if self.isVariable else self._z
        if z is None:
            return []
        return [zIntToZStr[x] for x in z]

    def getBaseInfo(self):
        natoms_str = "?" if self.is_remote_proxy else (
            f"{self.getNAtoms().min()}–{self.getNAtoms().max()}"
            if self.isVariable else str(self._natoms)
        )
        return [
            ("N. conf.", str(self._n)),
            ("N. atoms", natoms_str),
            ("Status", "Proxy (fetching…)" if self.is_remote_proxy else "Fetched"),
        ]

    def getInfo(self):
        has_forces = (
            (self._F_flat is not None) if self.isVariable else (self._F is not None)
        )
        return [
            ("Fingerprint", self.fingerprint[:12] + "…"),
            ("Energies", "yes" if self._E is not None else "no"),
            ("Forces", "yes" if has_forces else "no"),
            ("Variable", "yes" if self.isVariable else "no"),
        ]

    def getLattice(self):
        return None

    def isDependentOn(self, fp):
        return False

    # Bond matrix — only works after populate()
    def getBondMatrix(self, index):
        from scipy.spatial import distance_matrix

        if self.isVariable:
            # Variable: compute per-molecule bonds dynamically (same as
            # VariableDatasetLoader) because molecule sizes differ
            if self._R_flat is None or self._offsets is None:
                return np.zeros((1, 1), dtype=bool)
            from config.atoms import covalentBonds
            from config.userConfig import getConfig
            r = self.getCoordinates(index)
            z = self.getElements(index)
            bond_sizes = covalentBonds[z][:, z] * getConfig("loupeBondsLenience")
            d = distance_matrix(r, r)
            return d < bond_sizes
        else:
            # Uniform: use bondSizes precomputed in populate()
            if self.bondSizes is None or self._R is None:
                n = self._natoms or 1
                return np.zeros((n, n), dtype=bool)
            r = self.getCoordinates(index)
            d = distance_matrix(r, r)
            return d < self.bondSizes

    bondSizes = None
    chem = "?"

    @property
    def z(self):
        if self.isVariable:
            return self._z_flat if self._z_flat is not None else np.array([], dtype=np.int32)
        return self._z if self._z is not None else np.array([], dtype=np.int32)
