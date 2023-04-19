## Installation

Create a new python environment (conda/venv). It needs to be at least python 3.9

Install the following packages:

`pip install pyside6 pyqtgraph vispy pyopengl qasync scipy sklearn sgdml schnetpack`

## Basic usage

While inside the main folder and the appropriate python environment, simply run:

`python main.py`

### Models

Currently only sGDML, SchNet, MACE, Nequip and SpookyNet are _fully_ implemented. You can however also load prepredicted energies and forces in the "Models" menu. The format for this is simple: create a .npz file with energies under the "E" key and forces under the "F" key (same as sGDML npz datasets). You can then load this .npz file under "Model"->"Load prepredicted": note that this pre-predicted model needs to be loaded relative to an already loaded dataset (see bottom tab when loading prepredicted model).

### Datasets

Currently just .npz, others coming very soon

etc...

### 3D Visualiser 

A new 3D visualiser ("loupe") can be opened through the menu (Loupe -> New). From there, any loaded dataset can be selected and visualised. Some visualisation options can be found when opening the menu on the right-hand side of the loupe (collapsing arrow at the top right). 

Sub-datasets, e.g. zoomed-in plots, can also be displayed in a loupe by toggling the "Sub" checkbox on compatible plots. This will create a new dataset (dynamically updated when changing the plot's zoom/selection) that can also be opened in a loupe window.
