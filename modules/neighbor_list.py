import numpy as np
import itertools
import logging
from typing import Optional, Any

from ase.neighborlist import PrimitiveNeighborList, get_connectivity_matrix
from ase.geometry import conditional_find_mic

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust as needed (DEBUG/INFO/WARNING)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


def build_neighbor_list(atoms: Any, cutoffs: Optional[list] = None, **kwargs) -> 'AnglePrimitiveNeighborList':
    """
    Automatically build and update a neighbor list for a given ASE Atoms object.

    Parameters:
        atoms: ASE Atoms object.
        cutoffs: list of floats (optional)
            Radii for each atom. If not provided, natural cutoffs will be used.
        kwargs: Additional options to be passed to the neighbor list constructor.

    Returns:
        AnglePrimitiveNeighborList: Updated neighbor list instance.
    """
    logger.debug("Building neighbor list with cutoffs: %s and kwargs: %s", cutoffs, kwargs)
    nl = AnglePrimitiveNeighborList(cutoffs, **kwargs)
    nl.update(atoms.pbc, atoms.get_cell(complete=True), atoms.positions)
    return nl


def def_angle_threshold(cell: np.ndarray) -> float:
    """
    Define an angle threshold based on the unit vectors of the cell axes.

    Parameters:
        cell: 3x3 array representing the lattice cell.

    Returns:
        float: The computed angle threshold.
    """
    a = cell[0] / np.linalg.norm(cell[0])
    b = cell[1] / np.linalg.norm(cell[1])
    c = cell[2] / np.linalg.norm(cell[2])
    # Compute the minimum angle between cell vectors in degrees,
    # then use half of that value minus a constant (5) as threshold.
    angle_values = np.rad2deg(np.arccos([np.dot(a, b), np.dot(a, c), np.dot(c, b)]))
    threshold = np.min(angle_values) / 2 - 5
    logger.debug("Computed angle threshold: %.3f", threshold)
    return threshold


def get_angles_func(v0: np.ndarray, v1: np.ndarray, nv0: np.ndarray, nv1: np.ndarray) -> np.ndarray:
    """
    Compute the angles (in degrees) between pairs of vectors v0 and v1.

    Parameters:
        v0, v1: Arrays of vectors.
        nv0, nv1: Norms of v0 and v1 respectively.

    Returns:
        np.ndarray: Array of angles in degrees.
        
    Raises:
        ZeroDivisionError: If any norm in nv0 or nv1 is zero.
    """
    if (nv0 <= 0).any() or (nv1 <= 0).any():
        logger.error("Zero norm encountered in vector normalization.")
        raise ZeroDivisionError('Undefined angle due to zero norm')
    v0n = v0 / nv0[:, np.newaxis]
    v1n = v1 / nv1[:, np.newaxis]
    # Clip dot products to avoid numerical issues with arccos
    dot_products = np.einsum('ij,ij->i', v0n, v1n).clip(-1.0, 1.0)
    angles = np.arccos(dot_products)
    return np.degrees(angles)


class AnglePrimitiveNeighborList(PrimitiveNeighborList):
    """
    A customized neighbor list that filters neighbors based on an angle threshold.
    
    Attributes:
        angle_threshold (Optional[float]): Angle threshold in degrees.
    """
    def __init__(self, cutoffs, skin: float = 0.3, sorted: bool = False, 
                 self_interaction: bool = False, bothways: bool = True, 
                 use_scaled_positions: bool = False, angle_threshold: Optional[float] = None):
        super().__init__(cutoffs, skin, sorted, self_interaction, bothways, use_scaled_positions)
        self.angle_threshold = angle_threshold

    def build(self, pbc: np.ndarray, cell: np.ndarray, positions: np.ndarray, numbers: Optional[np.ndarray] = None) -> None:
        """
        Build the neighbor list and apply an angle-based filter to refine neighbor connectivity.
        
        Parameters:
            pbc: Periodic boundary conditions (array-like of booleans).
            cell: 3x3 lattice cell matrix.
            positions: Array of atomic positions.
            numbers: (Optional) Atomic numbers.
        """
        self.bothways = True
        super().build(pbc, cell, positions)
        # Determine the angle threshold: use the provided value or compute a default.
        angle_threshold = self.angle_threshold if self.angle_threshold is not None else (
            def_angle_threshold(cell) if pbc.all() else 60)
        logger.debug("Using angle threshold: %.3f", angle_threshold)

        natoms = len(positions)
        # Process each atom individually
        for atom in range(natoms):
            neis = np.unique(self.neighbors[atom])
            if len(neis) > 1:
                # Generate all unique pairs of neighbors (avoid self-interaction)
                indices = np.array([
                    [neis[i1], atom, neis[i2]]
                    for i1, i2 in itertools.combinations(range(len(neis)), 2)
                    if neis[i1] != atom and neis[i2] != atom
                ])
                if indices.size == 0:
                    continue

                # Extract positions for the three atoms in each triplet
                a1s = positions[indices[:, 0]]
                a2s = positions[indices[:, 1]]
                a3s = positions[indices[:, 2]]
                v12 = a1s - a2s
                v32 = a3s - a2s

                # Apply periodic minimum image convention
                (v12, v32), (nv12, nv32) = conditional_find_mic([v12, v32], cell=cell, pbc=pbc)
                angles = get_angles_func(v12, v32, nv12, nv32)

                # Identify the pairs with angles below the threshold
                mask = angles < angle_threshold
                indices_to_delete = indices[mask]
                nv12_masked, nv32_masked = nv12[mask], nv32[mask]

                # Use a set to avoid duplicates and determine which neighbors to remove
                neis_del = {
                    indx[int(bool_del_1) - 1]
                    for indx, bool_del_1 in zip(indices_to_delete, nv12_masked > nv32_masked)
                }
                if neis_del:
                    logger.debug("Atom %d: Removing neighbors %s based on angle criteria", atom, neis_del)
                self.neighbors[atom] = np.setdiff1d(neis, list(neis_del))

        # Ensure neighbor lists are symmetric (both ways)
        if self.bothways:
            neighbors2 = [[] for _ in range(natoms)]
            displacements2 = [[] for _ in range(natoms)]
            for a in range(natoms):
                for b, disp in zip(self.neighbors[a], self.displacements[a]):
                    neighbors2[b].append(a)
                    displacements2[b].append(-disp)
            for a in range(natoms):
                nbs = np.concatenate((self.neighbors[a], neighbors2[a]))
                disp = np.array(list(self.displacements[a]) + displacements2[a])
                self.neighbors[a] = nbs.astype(int)
                self.displacements[a] = disp.astype(int).reshape((-1, 3))
    
    def get_connectivity_matrix(self, sparse=True):
        """
        See :func:`~ase.neighborlist.get_connectivity_matrix`.
        """
        return get_connectivity_matrix(self, sparse)
