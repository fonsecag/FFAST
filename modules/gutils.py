import numpy as np
import scipy as sp
from ase.calculators.calculator import Calculator
from ase.data.vdw import vdw_radii as vdw_radii_ase
from sgdml.utils import desc
import logging

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust log level as needed (DEBUG/INFO/WARNING)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


class FakeCalc(Calculator):
    def __init__(self) -> None:
        super().__init__()


def get_vdw_radii_dict() -> dict:
    """
    Build a dictionary mapping atomic indices to their van der Waals radii.

    Returns:
        dict: Mapping {atomic_index: vdw_radius}.
    """
    vdw_radii = {atom: vdw for atom, vdw in enumerate(vdw_radii_ase)}
    logger.debug("Computed vdW radii dictionary with %d entries", len(vdw_radii))
    return vdw_radii


def pdistPBC(r: np.ndarray, lat_and_inv: tuple = None) -> np.ndarray:
    """
    Compute the pairwise Euclidean distance matrix between all atoms,
    accounting for periodic boundary conditions.

    Parameters:
        r (np.ndarray): Array of atomic coordinates (flattened to 3N).
        lat_and_inv (tuple, optional): Tuple (lattice, inverse lattice) for PBC correction.

    Returns:
        np.ndarray: Squareform distance matrix.
    """
    r = r.reshape(-1, 3)
    if lat_and_inv is None:
        pdist = sp.spatial.distance.pdist(r, metric='euclidean')
    else:
        try:
            pdist = sp.spatial.distance.pdist(
                r, lambda u, v: np.linalg.norm(desc._pbc_diff(u - v, lat_and_inv))
            )
        except Exception as e:
            logger.error("Error in pdistPBC: %s", e)
            raise e
    result = sp.spatial.distance.squareform(pdist, checks=False)
    logger.debug("pdistPBC computed distance matrix of shape %s", result.shape)
    return result


def center_of_mass_pbc(r: np.ndarray, masses: np.ndarray, lat_and_inv: tuple = None) -> tuple:
    """
    Calculate the center of mass for a set of positions and return the maximum distance
    from the center of mass (considering periodic boundary conditions if provided).

    Parameters:
        r (np.ndarray): Array of positions with shape (n_frames, n_atoms, 3).
        masses (np.ndarray): Atomic masses for each atom.
        lat_and_inv (tuple, optional): Tuple (lattice, inverse lattice) for PBC correction.

    Returns:
        tuple: (com, max_distance)
            - com: Center of mass (n_frames, 3).
            - max_distance: Maximum distance from the center of mass (scalar).
    """
    n_frames = len(r)
    # Compute weighted center of mass for each frame.
    com = np.average(r.reshape(n_frames, -1, 3), axis=1, weights=masses)
    # Calculate differences to the center of mass.
    dist_to_com = com[:, None, :] - r.reshape(n_frames, -1, 3)
    if lat_and_inv is not None:
        lattice, inv_lattice = lat_and_inv
        # Correct distances using the periodic boundary conditions.
        c = np.einsum('ij,kja->kia', inv_lattice, np.transpose(dist_to_com,(0,2,1)))
        dist_to_com -= np.transpose(np.einsum('ij,kja->kia', lattice, np.rint(c)), (0, 2, 1))
        max_distance = np.linalg.norm(dist_to_com, axis=2).max()
    else:
        max_distance = np.linalg.norm(dist_to_com, axis=2).max()
    logger.debug("Computed center of mass and max distance for %d frames", n_frames)
    return com, max_distance


def center_of_mass_pbc_wrapper(r: np.ndarray, masses: np.ndarray, lat_and_inv: tuple = None) -> tuple:
    """
    A wrapper for center_of_mass_pbc to be used as a utility function.

    Parameters:
        r (np.ndarray): Positions array.
        masses (np.ndarray): Atomic masses.
        lat_and_inv (tuple, optional): Lattice and its inverse.

    Returns:
        tuple: (center of mass, maximum distance to center)
    """
    return center_of_mass_pbc(r, masses, lat_and_inv)

