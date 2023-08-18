(Note: more complete documentation/tutorials coming soon)

## Installation

Create a new python environment (conda/venv). It needs to be at least python 3.9

Install the following packages:

`pip install pyside6==6.4.2 pyqtgraph vispy pyopengl qasync scipy scikit-learn ase torch`

Support for individual MLFF models are subject to their own installation process! For example for sgdml and SchNet:

`pip install sgdml schnetpack`

## Basic usage

While inside the main folder and the appropriate python environment, simply run:

`python main.py`

### Models

Currently only sGDML, SchNet, MACE, Nequip and SpookyNet are _fully_ implemented. You can however also load prepredicted energies and forces in the "Models" menu. The format for this is simple: create a .npz file with energies under the "E" key and forces under the "F" key (same as sGDML npz datasets). You can then load this .npz file under "Model"->"Load prepredicted": note that this pre-predicted model needs to be loaded relative to an already loaded dataset (see bottom tab when loading prepredicted model).

### Datasets

Currently .npz files (sGDML-style) and ase-supported datasets (.db, .extxy, .traj, ...).

### Data generation

Calculations (e.g. predictions, clusters, mae...) are automatically done on-the-fly in the UI. However, for expensive calculations (e.g. predictions) one can instead pre-compute them in headless mode with a simple script that can be run locally or on a remote node without any need of a UI. Both the headless and the UI client can save computed data for future use. 

An example of a simple headless script to compute the force prediction for a dataset/model combination is shown in `headless.py`. More tutorials on that soon...

### 3D Visualiser 

A new 3D visualiser ("loupe") can be opened through the menu (Loupe -> New). From there, any loaded dataset can be selected and visualised. 

Sub-datasets, e.g. zoomed-in plots, can also be displayed in a loupe by toggling the "Sub" toggle icon on compatible plots. This will create a new dataset (dynamically updated when changing the plot's zoom/selection) that can also be opened in a loupe window.

## Example

Four example models with pre-computed forces and energies are provided to immediately experiment with the tools. First, the datasets have to be loaded from the original source (http://www.sgdml.org/#datasets). The two datasets we focus on are the MD22 Docosahexaenoic acid and MD22 Stachyose and are available to be downloaded as npz files. 

Open the software by running `python main.py`, then load one or both datasets of interest (File -> Load Dataset or `CMD-D`). Then load the pre-predicted model folders (File -> Load or `CMD-L`), namely `examples/MACE` and `examples/Nequip`. Assuming the original datasets are unchanged, the program will automatically realise the pre-predictions belong to the respective datasets that were just loaded.

Pre-release reference: https://arxiv.org/abs/2308.06871 
