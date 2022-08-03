## Installation

Create a new python environment (conda/venv). It needs to be at least python 3.8, preferably 3.9.

Install the following packages:

`pip install pyside6 pyqtgraph vispy pyopengl qasync scipy sklearn sgdml`

### Basic usage

While inside the main folder and the appropriate python environment, simpl run:

`python main.py`

### Models

Currently only sGDML are _fully_ implemented. You can however also load prepredicted energies and forces in the "Models" menu. The format for this is simple: create a .npz file with energies under the "E" key and forces under the "F" key (same as sGDML npz datasets).

### Datasets

Currently just .npz, others coming very soon

etc...
