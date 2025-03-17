import ase
from ase.data import atomic_masses
import numpy as np
import scipy as sp
from tqdm import tqdm
from operator import itemgetter
import logging

# Import functions from our other modules
from modules.gutils import FakeCalc, get_vdw_radii_dict, center_of_mass_pbc

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust as needed (DEBUG/INFO/WARNING)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)



def createTraj(R: np.ndarray, z: np.ndarray, F: np.ndarray = None, E: np.ndarray = None, lattice: np.ndarray = None) -> list:
    """
    Create a list of ASE Atoms objects from trajectory arrays.

    Parameters:
        R (np.ndarray): Coordinates with shape (n_frames, n_atoms, 3).
        z (np.ndarray): Atomic numbers for each atom.
        F (np.ndarray, optional): Forces for each frame.
        E (np.ndarray, optional): Energies for each frame.
        lattice (np.ndarray, optional): Lattice vectors; if provided, should be
            an array that can be transposed appropriately.

    Returns:
        list: List of ASE Atoms objects.
    """
    traj = []
    for i, r in enumerate(R):
        cell = lattice if lattice is None else lattice.T
        pbc = 3 * [False] if lattice is None else 3 * [True]
        atoms = ase.Atoms(positions=r, numbers=z, cell=cell, pbc=pbc)
        atoms.calc = FakeCalc()
        atoms.calc.results = {
            'forces': np.zeros_like(r) if F is None else F[i],
            'energy': 0.0 if E is None else E[i],
        }
        traj.append(atoms)
    logger.debug("Created trajectory with %d frames", len(traj))
    return traj


def CoarseGrainTraj(traj: list, comp_pos: np.ndarray) -> tuple:
    """
    Coarse grain the trajectory by combining atoms that belong to the same component.

    The algorithm calculates the center of mass of grouped atoms, updates the trajectory,
    and modifies the van der Waals radii dictionary accordingly.

    Parameters:
        traj (list): List of ASE Atoms objects.
        comp_pos (np.ndarray): Array indicating the component index for each atom.

    Returns:
        tuple: (traj_eff, vdw_radii, atom_new_order)
            - traj_eff: The coarse-grained trajectory (list of ASE Atoms objects).
            - vdw_radii: Updated van der Waals radii dictionary.
            - atom_new_order: New ordering of atoms after coarse graining.
    """
    import hashlib

    vdw_radii = get_vdw_radii_dict()
    R = np.array([t.positions for t in traj])
    lat_and_inv = (traj[0].cell.T, np.linalg.inv(traj[0].cell.T)) if traj[0].cell is not None else None
    z = traj[0].numbers

    R_temp = np.copy(R)
    mask_list = []
    com_list = []
    z_list = []
    new_atom = len(z)

    comp_uniq, comp_count = np.unique(comp_pos, return_counts=True)
    z_temp = np.copy(z)
    for uniq, count in tqdm(zip(comp_uniq, comp_count), total=len(comp_uniq), desc="CoarseGraining"):
        if (count > 0) and (count < comp_count.max()):
            mask = np.where(comp_pos == uniq)
            masses = atomic_masses[z[mask]]
            com, d_to_com = center_of_mass_pbc(R[:, mask], masses, lat_and_inv)
            # Mark grouped atoms as removed using np.nan
            R_temp[:, mask] = np.nan
            # Create a unique identifier for the component using hashing
            z_comp = abs(hash(''.join(map(str, np.sort(z_temp[mask]))))) % (10 ** 8)
            # Update vdw radii dictionary: maximum vdw radius of grouped atoms plus distance correction
            vdw_radii[z_comp] = np.array(itemgetter(*z_temp[mask])(vdw_radii)).max() + d_to_com
            z_temp[mask] = 0
            z_list.append(z_comp)
            mask_list.append(mask)
            new_atom -= (len(mask[0]) - 1)
            com_list.append(com.squeeze())

    n_frames = len(traj)
    # Build effective positions array; note that NaNs are removed then reshaped appropriately.
    R_eff = np.zeros((n_frames, new_atom, 3))
    R_temp_clean = R_temp[~np.isnan(R_temp)].reshape(n_frames, -1, 3)
    R_eff[:, :R_temp_clean.shape[1], :] = R_temp_clean
    # Append centers of mass for the coarse-grained groups.
    R_eff[:, R_temp_clean.shape[1]:, :] = np.column_stack(com_list).reshape(n_frames, len(com_list), 3)

    z_eff = np.zeros(new_atom, dtype=np.int64)
    mask_index = np.vstack(mask_list)  # Note: This assumes consistent mask sizes.
    z_eff[:R_temp_clean.shape[1]] = np.delete(z, mask_index.flatten()).astype(np.int64)
    logger.debug("z_eff dtype after deletion: %s", z_eff.dtype)
    z_eff[R_temp_clean.shape[1]:] = np.array(z_list).flatten().astype(np.int64)
    logger.debug("Final z_eff: %s", z_eff)

    # Construct new atom order; note that this might require further refinement.
    atom_new_order = new_atom * [0.0]
    atom_new_order[:R_temp_clean.shape[1]] = np.delete(np.arange(len(z)), mask_index.flatten())[:, None]
    atom_new_order[R_temp_clean.shape[1]:] = mask_index

    traj_eff = createTraj(R_eff, z_eff, lattice=traj[0].cell.T)
    logger.info("Coarse graining completed: %d new atoms", new_atom)
    return traj_eff, vdw_radii, atom_new_order


def FineGrainTraj(adj_matr_eff: np.ndarray, adj_matr: np.ndarray, atom_new_order: np.ndarray) -> np.ndarray:
    """
    Refine the connectivity graph by incorporating effective adjacencies.

    Parameters:
        adj_matr_eff (np.ndarray): Effective adjacency matrix from coarse graining.
        adj_matr (np.ndarray): Original adjacency matrix.
        atom_new_order (np.ndarray): New atom order mapping from coarse graining.

    Returns:
        np.ndarray: Refined (fine-grained) adjacency matrix.
    """
    # Build dictionaries of neighbors for effective and original graphs.
    adj_dict_eff = {i: np.where(row != 0)[0].tolist() for i, row in enumerate(adj_matr_eff)}
    adj_dict = {i: np.where(row != 0)[0].tolist() for i, row in enumerate(adj_matr)}

    for i, elements in enumerate(atom_new_order):
        for elem in elements:
            # Merge neighbor lists and ensure uniqueness
            adj_dict[elem] = np.unique(adj_dict[elem] + adj_dict_eff[i]).tolist()
    # Build the fine-grained adjacency matrix from the merged dictionary.
    n = len(adj_dict)
    adj_matr_fine = np.zeros((n, n))
    for i, elements in adj_dict.items():
        adj_matr_fine[i, elements] = 1
    logger.info("Fine graining of trajectory completed")
    return adj_matr_fine