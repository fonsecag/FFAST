import numpy as np
import scipy as sp
from tqdm import tqdm
from time import time
from joblib import Parallel, delayed
import logging

# Import functions from our other modules
from modules.trajectory_processing import createTraj, CoarseGrainTraj, FineGrainTraj, get_vdw_radii_dict
from modules.neighbor_list import build_neighbor_list

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Change to INFO or WARNING in production
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


def GFilter(adj_matrices: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    """
    Filter and binarize the adjacency matrices based on a frequency threshold.

    Parameters:
        adj_matrices (np.ndarray): 3D array of shape (n_frames, n_atoms, n_atoms).
        threshold (float): Threshold as a fraction of the number of frames.

    Returns:
        np.ndarray: A binary (0/1) adjacency matrix.
    """
    n_frames = len(adj_matrices)
    adjs_sum = np.array(adj_matrices).sum(axis=0)
    adj_matrix = np.copy(adjs_sum)

    # Thresholding: if the sum is less than n_frames * threshold, set to zero.
    adj_matrix[adj_matrix < n_frames * threshold] = 0
    adj_matrix[adj_matrix != 0] = 1
    logger.debug("GFilter: Processed adjacency matrix with threshold %.2f", threshold)
    return adj_matrix


def GraphConstr(traj: list, cutoffs: list, threshold: float = 0.9, angle_threshold: float = None) -> tuple:
    """
    Construct connectivity graphs (adjacency matrices) for each frame in the trajectory.

    Parameters:
        traj (list): List of ASE Atoms objects.
        cutoffs (list): Cutoff radii for building neighbor lists.
        threshold (float): Frequency threshold to filter edges.
        angle_threshold (float, optional): Angle threshold for refining neighbor connectivity.

    Returns:
        tuple: (adj_matrix, adj_matrices)
            - adj_matrix: The filtered (binary) adjacency matrix.
            - adj_matrices: The raw adjacency matrices for each frame.
    """
    logger.info("Starting GraphConstr...")
    t1 = time()
    n_frames = len(traj)
    n_atoms = len(traj[0])
    logger.debug("Trajectory contains %d frames with %d atoms each.", n_frames, n_atoms)

    # Build neighbor lists in parallel.
    def process_atoms(atoms, cutoffs, angle_threshold):
        return build_neighbor_list(
            atoms,
            cutoffs=cutoffs,
            self_interaction=True,
            bothways=True,
            angle_threshold=angle_threshold,
        )

    neighbors = Parallel(n_jobs=-1, backend="loky")(
        delayed(process_atoms)(atoms, cutoffs, angle_threshold) for atoms in tqdm(traj, desc="Processing Atoms")
    )
    t2 = time()
    logger.info("GraphConstr Step 1 completed in %.3f seconds.", t2 - t1)

    # Build adjacency matrices from neighbor lists.
    adj_matrices = np.zeros((n_frames, n_atoms, n_atoms))
    for i, nl in enumerate(tqdm(neighbors, desc="Building Adjacency Matrices")):
        adj_matrices[i] = nl.get_connectivity_matrix(sparse=False)
    t3 = time()
    logger.info("GraphConstr Step 2 completed in %.3f seconds.", t3 - t2)

    # Filter the aggregated adjacency matrix.
    adj_matrix = GFilter(adj_matrices, threshold=threshold)
    # Zero out the diagonal entries.
    np.fill_diagonal(adj_matrix, 0)
    t4 = time()
    logger.info("GraphConstr Step 3 completed in %.3f seconds.", t4 - t3)
    return adj_matrix, adj_matrices


def FinalGraphConstruct(traj: list, lattice: np.ndarray, angle_threshold: float, freq_threshold: float) -> list:
    """
    Build the final connectivity graph and extract bond list from the trajectory.

    Parameters:
        traj (list): List of ASE Atoms objects.
        lattice (np.ndarray): Lattice cell matrix.
        angle_threshold (float): Angle threshold for neighbor list refinement.
        freq_threshold (float): Frequency threshold for edge filtering.

    Returns:
        list: List of bonds represented as tuples.
    """
    logger.info("Starting FinalGraphConstruct...")
    z = traj[0].numbers
    vdw_radii = get_vdw_radii_dict()
    cutoffs = np.array([vdw_radii[i] for i in z])
    adj_filt, _ = GraphConstr(traj, cutoffs=cutoffs, threshold=freq_threshold, angle_threshold=angle_threshold)

    comp_num, comp_pos = sp.sparse.csgraph.connected_components(adj_filt, directed=False)
    logger.info("Connected components: %s", comp_pos)
    logger.info("Graph has %d components.", comp_num)

    # If multiple components exist, coarse-grain the trajectory.
    if comp_num > 1:
        traj_eff, vdw_radii, atom_new_order = CoarseGrainTraj(traj, comp_pos)
        traj = traj_eff
        logger.debug("Updated vdw_radii dict: %s", vdw_radii)
        logger.debug("Trajectory atomic numbers: %s", traj_eff[0].numbers)
        cutoffs = np.array([vdw_radii[i] for i in traj_eff[0].numbers])
        adj_filt_eff, _ = GraphConstr(traj_eff, cutoffs=cutoffs, threshold=0.9999, angle_threshold=angle_threshold)
        # Fine grain the adjacency matrix based on the coarse-grained mapping.
        adj_filt = FineGrainTraj(adj_filt_eff, adj_filt, atom_new_order)

    # Construct bond list from the adjacency matrix.
    bondList = [(i, j + i) for i, row in enumerate(adj_filt) for j in np.where(row[i:] != 0)[0]]
    logger.info("FinalGraphConstruct: Bond list contains %d bonds.", len(bondList))
    return bondList


def BondsToAdj(bondList: list, n_atoms: int) -> tuple:
    """
    Convert a list of bonds into an adjacency dictionary and matrix.

    Parameters:
        bondList (list): List of bonds (tuples) where each bond is (i, j).
        n_atoms (int): Total number of atoms.

    Returns:
        tuple: (adjDict, adjsMatrix)
            - adjDict: Dictionary mapping each atom to its neighbors.
            - adjsMatrix: Adjacency matrix (numpy.ndarray).
    """
    adjDict = {}
    adjsMatrix = np.zeros((n_atoms, n_atoms))
    for bond in bondList:
        i, j = bond
        adjsMatrix[i, j] = 1
        adjDict.setdefault(i, []).append(j)
        adjsMatrix[j, i] = 1
        adjDict.setdefault(j, []).append(i)
    logger.debug("BondsToAdj: Created adjacency dictionary and matrix for %d atoms.", n_atoms)
    return adjDict, adjsMatrix


def ffastInterfaceGraphConstruct(R: np.ndarray, z: np.ndarray, lattice: np.ndarray, 
                                  angle_threshold: float, freq_threshold: float) -> list:
    """
    Fast interface to construct a connectivity graph from trajectory arrays.

    Parameters:
        R (np.ndarray): Coordinate array for the trajectory.
        z (np.ndarray): Atomic numbers.
        lattice (np.ndarray): Lattice cell matrix.
        angle_threshold (float): Angle threshold for neighbor list filtering.
        freq_threshold (float): Frequency threshold for graph filtering.

    Returns:
        list: Bond list generated from the final graph construction.
    """
    aseTraj = createTraj(R, z, lattice=lattice)
    bondList = FinalGraphConstruct(aseTraj, lattice, angle_threshold, freq_threshold)
    logger.info("ffastInterfaceGraphConstruct: Completed bond list with %d bonds.", len(bondList))
    return bondList
