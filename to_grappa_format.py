#%%
from pathlib import Path
import numpy as np
from grappa.data import MolData
from grappa.utils import openmm_utils, openff_utils

def to_grappa_format(path, forcefield, forcefield_type='openmm', charge_model='classical', target_path=None):
    """
    Converts the psi4_energies.npy and psi4_forces.npy files in the given folder to a format that can be read by grappa. 
    """
    assert path.is_dir(), "The given path is not a directory."

    if target_path is None:
        target_path = path

    energy = np.load(path/"psi4_energies.npy")
    gradient = -np.load(path/"psi4_forces.npy")

    xyz = np.load(path/"positions.npy")
    atomic_numbers = np.load(path/"atomic_numbers.npy") # not needed

    pdbstring = open(path/"pep.pdb").read()

    sequence = path.stem

    smiles = str(np.load(path/"smiles.npy"))
    mapped_smiles = str(np.load(path/"mapped_smiles.npy"))

    valid_idxs = np.isfinite(energy)
    valid_idxs = np.where(valid_idxs)[0]
    energy = energy[valid_idxs]
    gradient = gradient[valid_idxs]
    xyz = xyz[valid_idxs]


    if forcefield_type == 'openmm':
        # get topology:
        topology = openmm_utils.topology_from_pdb(pdbstring)
        smiles = None
        ff = openmm_utils.get_openmm_forcefield(forcefield)
        system = ff.createSystem(topology)
        mol_id = smiles

    elif forcefield_type == 'openff' or forcefield_type == 'openmmforcefields':
        openff_mol = openff_utils.mol_from_pdb(pdbstring)
        mol_id = smiles
        system, topology, _ = openff_utils.get_openmm_system(mapped_smiles=None, openff_forcefield=forcefield, openff_mol=openff_mol)
    else:
        raise ValueError(f"forcefield_type must be either openmm, openff or openmmforcefields but is {forcefield_type}")

    # create moldata object from the system (calculate the parameters, nonbonded forces and create reference energies and gradients from that)
    moldata = MolData.from_openmm_system(openmm_system=system, openmm_topology=topology, xyz=xyz, gradient=gradient, energy=energy, mol_id=mol_id, pdb=pdbstring, smiles=smiles, sequence=sequence, allow_nan_params=True, charge_model=charge_model, ff_name=forcefield)

    openmm_gradients = moldata.ff_gradient[forcefield]
    
    # calculate the crmse:
    crmse = np.sqrt(np.mean((openmm_gradients-gradient)**2))
    if crmse > 15:
        print(f"Warning: crmse between {forcefield} and QM is {round(crmse, 1)} for {path.stem}, std of gradients is {round(np.std(gradient), 1)}")


    moldata.save(target_path/(path.stem+'.npz'))

    return


def convert_dataset(path, forcefield, forcefield_type='openmm', charge_model='classical', target_path=None):
    """
    Converts the psi4_energies.npy and psi4_forces.npy files in the given folder to a format that can be read by grappa. 
    """
    assert path.is_dir(), "The given path is not a directory."

    if target_path is not None:
        target_path = Path(target_path)
        target_path.mkdir(parents=True, exist_ok=True)
        

    print()
    for i, subdir in enumerate(path.iterdir()):
        print(f"Processing {i+1}: {subdir.stem}      ", end="\r")
        try:
            if subdir.is_dir():
                to_grappa_format(subdir, forcefield, forcefield_type, charge_model, target_path)
        except Exception as e:
            print()
            raise e

    print()
    
    return


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source_path", type=str, help="Path to the folder with subfolders that contain psi4_energies.npy and psi4_forces.npy files."
    )
    parser.add_argument(
        "--target_path", type=str, help="Path to the target folder in which the dataset is stored as collection of npz files."
    )
    parser.add_argument(
        "--forcefield", type=str, default="amber99sbildn", help="Forcefield to use for the conversion."
    )
    parser.add_argument(
        "--forcefield_type", type=str, default="openmm", help="Type of forcefield to use for the conversion. Available: openmm, openff, openmmforcefields."
    )
    parser.add_argument(
        "--charge_model", type=str, default="classical", help="Charge model of the underlying forcefield. Available: classical, am1BCC"
    )
    args = parser.parse_args()

    source_path = Path(args.source_path)
    target_path = Path(args.target_path) if args.target_path is not None else None
    forcefield = args.forcefield
    forcefield_type = args.forcefield_type
    charge_model = args.charge_model

    convert_dataset(source_path, forcefield, forcefield_type, charge_model, target_path)