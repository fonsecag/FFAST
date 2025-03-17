import numpy as np
import scipy as sp
from tqdm import tqdm
from sgdml.utils import perm
from pynauty import Graph, autgrp
import logging

# Import functions from our other modules
from modules.trajectory_processing import createTraj
from modules.gutils import get_vdw_radii_dict, pdistPBC
from modules.graph_construction import GraphConstr, CoarseGrainTraj, FineGrainTraj, BondsToAdj

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust log level as needed
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


def rotor_symmetry(orbits: np.ndarray, adj_dict: dict) -> dict:
    """
    Apply rotor symmetry adjustments for orbits with three elements.
    
    For each rotor orbit (where count == 3), update the adjacency dictionary by
    appending the cyclic neighbor for each element.

    Parameters:
        orbits (np.ndarray): Array representing orbit labels for atoms.
        adj_dict (dict): Dictionary mapping atom indices to lists of neighbor indices.

    Returns:
        dict: Updated adjacency dictionary.
    """
    uniq, counts = np.unique(orbits, return_counts=True)
    rot_orbits = uniq[counts == 3]
    logger.debug("Found %d rotor orbits (count==3)", len(rot_orbits))
    
    for rotor in rot_orbits:
        rotor_elements = np.where(orbits == rotor)[0]
        for i, elem in enumerate(rotor_elements):
            next_elem = rotor_elements[(i + 1) % len(rotor_elements)]
            adj_dict.setdefault(elem, []).append(next_elem)
            logger.debug("Rotor symmetry: Atom %d appended neighbor %d", elem, next_elem)
    return adj_dict


def broken_rotor_symmetry(orbits: np.ndarray, adj_dict: dict, z: np.ndarray) -> dict:
    """
    Adjust the adjacency dictionary for broken rotor symmetry (rotors with two elements).

    For each rotor orbit (count == 2) associated with hydrogen (atomic number 1),
    identify a common vertex and adjust the neighbor list if conditions are met.

    Parameters:
        orbits (np.ndarray): Array of orbit labels.
        adj_dict (dict): Adjacency dictionary.
        z (np.ndarray): Array of atomic numbers.

    Returns:
        dict: Updated adjacency dictionary.
    """
    uniq, counts = np.unique(orbits, return_counts=True)
    rot_orbits = uniq[counts == 2]
    logger.debug("Found %d broken rotor orbits (count==2)", len(rot_orbits))
    
    for rotor in rot_orbits:
        rotor_elements = np.where(orbits == rotor)[0]
        if 1 in z[rotor_elements]:  # assume hydrogen rotor
            common_vert = [val for val in adj_dict.get(rotor_elements[0], []) 
                           if val in adj_dict.get(rotor_elements[1], [])]
            if len(common_vert) != 1:
                logger.debug("Broken rotor symmetry: Skipping rotor %s due to ambiguous common vertex", rotor)
                break
            elif np.array(adj_dict.get(common_vert[0], []))[np.array(adj_dict.get(common_vert[0], [])) == 1].sum() == 3:
                adj_dict.setdefault(rotor_elements[0], []).append(rotor_elements[1])
                logger.debug("Broken rotor symmetry: Added edge between %d and %d", rotor_elements[0], rotor_elements[1])
    return adj_dict


def sgdml_perm(traj: list, lattice: np.ndarray, mask: np.ndarray) -> list:
    """
    Compute permutations using the sGDML method for a masked subset of atoms.

    Parameters:
        traj (list): List of ASE Atoms objects.
        lattice (np.ndarray): Lattice cell matrix.
        mask (np.ndarray): Boolean or index mask for selecting atoms.

    Returns:
        list: List of permutations.
    """
    lat_and_inv = (lattice.T, np.linalg.inv(lattice.T)) if lattice is not None else None
    R = np.array([t.positions[mask] for t in traj])
    z = traj[0].numbers[mask]
    logger.debug("Running sgdml_perm with %d atoms selected", len(z))
    perms = perm.find_perms(R, z, lat_and_inv=lat_and_inv, callback=None, max_processes=None)
    logger.info("sgdml_perm: Found %d permutations", len(perms))
    return perms


def add_permutations(permut_gen: list, permuts: list, mask: np.ndarray) -> list:
    """
    Extend a permutation generator list by combining new permutations.

    For each new permutation, update the inclusion indices for the masked atoms,
    and then combine with previously generated permutations.

    Parameters:
        permut_gen (list): List of existing permutations.
        permuts (list): List of new permutations to incorporate.
        mask (np.ndarray): Boolean or index mask for atoms.

    Returns:
        list: Combined list of permutations.
    """
    n_atoms = len(mask)
    n_permut = len(permut_gen)
    for perm in permuts:
        perm_inclus = np.arange(n_atoms)
        # Update only positions defined by mask
        perm_inclus[mask] = perm_inclus[mask][perm]
        permut_gen.append(perm_inclus)
        logger.debug("Added new permutation: %s", perm_inclus)
    
    permuts_result = []
    # Combine old and new permutations to generate the full set.
    for perm_old in permut_gen[:n_permut]:
        for perm_new in permut_gen[n_permut:]:
            combined = perm_old[perm_new]
            permuts_result.append(combined)
            logger.debug("Combined permutation: %s", combined)
    
    if not permuts_result:
        permuts_result = permut_gen
    logger.info("add_permutations: Total permutations count %d", len(permuts_result))
    return permuts_result


class GraphSymSer:
    """
    Class to handle graph-based symmetry search and recovery for atomic structures.
    """

    def __init__(self, R: np.ndarray, z: np.ndarray, lattice: np.ndarray, n_configs: int, 
                 angle_threshold: float, freq_threshold: float) -> None:
        """
        Initialize the symmetry search using a subset of the trajectory.

        Parameters:
            R (np.ndarray): Array of atomic positions (trajectory).
            z (np.ndarray): Array of atomic numbers.
            lattice (np.ndarray): Lattice cell matrix.
            n_configs (int): Number of configurations to sample.
            angle_threshold (float): Angle threshold for neighbor list filtering.
            freq_threshold (float): Frequency threshold for graph filtering.
        """
        self.indx = np.random.choice(len(R), n_configs, replace=False)
        if lattice.shape == (len(R), 3, 3):
            self.aseTraj = createTraj(R[self.indx], z, lattice=lattice[self.indx])
        else:
            self.aseTraj = createTraj(R[self.indx], z, lattice=lattice)
        self.angle_threshold = angle_threshold
        self.freq_threshold = freq_threshold
        logger.info("GraphSymSer initialized with %d configurations", n_configs)

    def runFinalGraphConstruct(self) -> list:
        """
        Construct the final connectivity graph and extract the bond list.

        Returns:
            list: Bond list represented as tuples (i, j).
        """
        z = self.aseTraj[0].numbers
        vdw_radii = get_vdw_radii_dict()
        cutoffs = np.array([vdw_radii[i] for i in z])
        adjs_filt, _ = GraphConstr(self.aseTraj, cutoffs=cutoffs, threshold=self.freq_threshold, 
                                   angle_threshold=self.angle_threshold)
        comp_num, comp_pos = sp.sparse.csgraph.connected_components(adjs_filt, directed=False)
        logger.info("Connected components: %s", comp_pos)
        logger.info("Graph has %d components", comp_num)
        
        traj = self.aseTraj.copy()
        if comp_num > 1:
            traj_eff, vdw_radii, atom_new_order = CoarseGrainTraj(traj, comp_pos)
            traj = traj_eff
            logger.debug("Coarse graining updated vdW radii: %s", vdw_radii)
            cutoffs = np.array([vdw_radii[i] for i in traj_eff[0].numbers])
            adjs_filt_eff, _ = GraphConstr(traj_eff, cutoffs=cutoffs, threshold=0.9999, 
                                           angle_threshold=self.angle_threshold)
            adjs_filt = FineGrainTraj(adjs_filt_eff, adjs_filt, atom_new_order)
        self.bondList = [(i, j + i) for i, row in enumerate(adjs_filt) for j in np.where(row[i:] != 0)[0]]
        logger.info("Final graph constructed with %d bonds", len(self.bondList))
        return self.bondList

    def runSymmRecover(self) -> tuple:
        """
        Recover symmetry information by computing permutation groups for the graph.
        Uses sGDML for small fragments and pynauty for larger fragments.

        Returns:
            tuple: (permut_num, placeholder, orb_num)
                   'placeholder' is currently set to 0.
        """
        use_sgdml_perm = True
        n_atoms = len(self.aseTraj[0])
        lattice = self.aseTraj[0].cell
        z = self.aseTraj[0].numbers
        R = np.array([trj.positions for trj in self.aseTraj])
        lat_and_inv = (lattice, np.linalg.inv(lattice)) if lattice is not None else None
        adjDict, adjsMatrix = BondsToAdj(self.bondList, n_atoms)
        permut_gen = []
        n_perms_max = 1

        graph = Graph(n_atoms, adjacency_dict=adjDict, 
                      vertex_coloring=[set(np.where(z == elem)[0]) for elem in np.unique(z)])
        perms, permut_num, permut_num_order, orb_pos, orb_num = autgrp(graph)
        comp_num, comp_pos = sp.sparse.csgraph.connected_components(adjsMatrix, directed=False)

        for comp in tqdm(range(comp_num), desc="Symmetry recovery"):
            min_cell_length = np.linalg.norm(lattice, axis=-1).min()
            mask_atoms_comp = (comp_pos == comp)
            comp_dist = pdistPBC(R[0][mask_atoms_comp].flatten(), lat_and_inv)
            isFragmSmall = not (comp_dist >= min_cell_length / 2).any()
            if isFragmSmall and use_sgdml_perm:
                perms_comp = perm.find_perms(R[:, mask_atoms_comp, :], z[mask_atoms_comp], 
                                             lat_and_inv=lat_and_inv, callback=None, max_processes=4)
                n_perms_max *= len(perms_comp)
            else:
                adjMatrix_masked = adjsMatrix[mask_atoms_comp, :][:, mask_atoms_comp]
                color_vert_list = [set(np.where(z[mask_atoms_comp] == elem)[0])
                                   for elem in np.unique(z[mask_atoms_comp])]
                adjDict_masked = {i: np.nonzero(row)[0].tolist() for i, row in enumerate(adjMatrix_masked)}
                graph_comp = Graph(mask_atoms_comp.sum(), adjacency_dict=adjDict_masked, vertex_coloring=color_vert_list)
                perms_comp, pnum, pnum_order, _, _ = autgrp(graph_comp)
                n_perms_max *= (pnum * 10 ** pnum_order)
                perms_comp.insert(0, list(range(mask_atoms_comp.sum())))
                perms_comp = np.array(perms_comp)
                permut_gen = add_permutations(permut_gen, perms_comp, mask_atoms_comp)
        permut_num = n_perms_max
        logger.info("Symmetry recovery: %d permutations, orb_num=%d", permut_num, orb_num)
        return permut_num, 0, orb_num
