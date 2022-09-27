## Installation

Create a new python environment (conda/venv). It needs to be at least python 3.9

Install the following packages:

`pip install pyside6 pyqtgraph vispy pyopengl qasync scipy sklearn sgdml schnetpack`

## Basic usage

While inside the main folder and the appropriate python environment, simply run:

`python main.py`

### Models

Currently only sGDML and SchNet are _fully_ implemented. You can however also load prepredicted energies and forces in the "Models" menu. The format for this is simple: create a .npz file with energies under the "E" key and forces under the "F" key (same as sGDML npz datasets). You can then load this .npz file under "Model"->"Load prepredicted": note that this pre-predicted model needs to be loaded relative to an already loaded dataset (see bottom tab when loading prepredicted model).

### Datasets

Currently just .npz, others coming very soon

etc...
