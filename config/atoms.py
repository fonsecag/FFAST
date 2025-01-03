import numpy as np

# http://jmol.sourceforge.net/jscolors/
atomColors = 255 * np.array(
    [
        [1, 0.8, 0.15],  # 0 is "All atoms"
        [1.000, 1.000, 1.000],  # H
        [0.851, 1.000, 1.000],  # He
        [0.800, 0.502, 1.000],  # Li
        [0.761, 1.000, 0.000],  # Be
        [1.000, 0.710, 0.710],  # B
        [0.565, 0.565, 0.565],  # C
        [0.188, 0.314, 0.973],  # N
        [1.000, 0.051, 0.051],  # O
        [0.565, 0.878, 0.314],  # F
        [0.702, 0.890, 0.961],  # Ne
        [0.671, 0.361, 0.949],  # Na
        [0.541, 1.000, 0.000],  # Mg
        [0.749, 0.651, 0.651],  # Al
        [0.941, 0.784, 0.627],  # Si
        [1.000, 0.502, 0.000],  # P
        [1.000, 1.000, 0.188],  # S
        [0.122, 0.941, 0.122],  # Cl
        [0.502, 0.820, 0.890],  # Ar
        [0.561, 0.251, 0.831],  # K
        [0.239, 1.000, 0.000],  # Ca
        [0.902, 0.902, 0.902],  # Sc
        [0.749, 0.761, 0.780],  # Ti
        [0.651, 0.651, 0.671],  # V
        [0.541, 0.600, 0.780],  # Cr
        [0.612, 0.478, 0.780],  # Mn
        [0.878, 0.400, 0.200],  # Fe
        [0.941, 0.565, 0.627],  # Co
        [0.314, 0.816, 0.314],  # Ni
        [0.784, 0.502, 0.200],  # Cu
        [0.490, 0.502, 0.690],  # Zn
        [0.761, 0.561, 0.561],  # Ga
        [0.400, 0.561, 0.561],  # Ge
        [0.741, 0.502, 0.890],  # As
        [1.000, 0.631, 0.000],  # Se
        [0.651, 0.161, 0.161],  # Br
        [0.361, 0.722, 0.820],  # Kr
        [0.439, 0.180, 0.690],  # Rb
        [0.000, 1.000, 0.000],  # Sr
        [0.580, 1.000, 1.000],  # Y
        [0.580, 0.878, 0.878],  # Zr
        [0.451, 0.761, 0.788],  # Nb
        [0.329, 0.710, 0.710],  # Mo
        [0.231, 0.620, 0.620],  # Tc
        [0.141, 0.561, 0.561],  # Ru
        [0.039, 0.490, 0.549],  # Rh
        [0.000, 0.412, 0.522],  # Pd
        [0.753, 0.753, 0.753],  # Ag
        [1.000, 0.851, 0.561],  # Cd
        [0.651, 0.459, 0.451],  # In
        [0.400, 0.502, 0.502],  # Sn
        [0.620, 0.388, 0.710],  # Sb
        [0.831, 0.478, 0.000],  # Te
        [0.580, 0.000, 0.580],  # I
        [0.259, 0.620, 0.690],  # Xe
        [0.341, 0.090, 0.561],  # Cs
        [0.000, 0.788, 0.000],  # Ba
        [0.439, 0.831, 1.000],  # La
        [1.000, 1.000, 0.780],  # Ce
        [0.851, 1.000, 0.780],  # Pr
        [0.780, 1.000, 0.780],  # Nd
        [0.639, 1.000, 0.780],  # Pm
        [0.561, 1.000, 0.780],  # Sm
        [0.380, 1.000, 0.780],  # Eu
        [0.271, 1.000, 0.780],  # Gd
        [0.188, 1.000, 0.780],  # Tb
        [0.122, 1.000, 0.780],  # Dy
        [0.000, 1.000, 0.612],  # Ho
        [0.000, 0.902, 0.459],  # Er
        [0.000, 0.831, 0.322],  # Tm
        [0.000, 0.749, 0.220],  # Yb
        [0.000, 0.671, 0.141],  # Lu
        [0.302, 0.761, 1.000],  # Hf
        [0.302, 0.651, 1.000],  # Ta
        [0.129, 0.580, 0.839],  # W
        [0.149, 0.490, 0.671],  # Re
        [0.149, 0.400, 0.588],  # Os
        [0.090, 0.329, 0.529],  # Ir
        [0.816, 0.816, 0.878],  # Pt
        [1.000, 0.820, 0.137],  # Au
        [0.722, 0.722, 0.816],  # Hg
        [0.651, 0.329, 0.302],  # Tl
        [0.341, 0.349, 0.380],  # Pb
        [0.620, 0.310, 0.710],  # Bi
        [0.671, 0.361, 0.000],  # Po
        [0.459, 0.310, 0.271],  # At
        [0.259, 0.510, 0.588],  # Rn
        [0.259, 0.000, 0.400],  # Fr
        [0.000, 0.490, 0.000],  # Ra
        [0.439, 0.671, 0.980],  # Ac
        [0.000, 0.729, 1.000],  # Th
        [0.000, 0.631, 1.000],  # Pa
        [0.000, 0.561, 1.000],  # U
        [0.000, 0.502, 1.000],  # Np
        [0.000, 0.420, 1.000],  # Pu
        [0.329, 0.361, 0.949],  # Am
        [0.471, 0.361, 0.890],  # Cm
        [0.541, 0.310, 0.890],  # Bk
        [0.631, 0.212, 0.831],  # Cf
        [0.702, 0.122, 0.831],  # Es
        [0.702, 0.122, 0.729],  # Fm
        [0.702, 0.051, 0.651],  # Md
        [0.741, 0.051, 0.529],  # No
        [0.780, 0.000, 0.400],  # Lr
        [0.800, 0.000, 0.349],  # Rf
        [0.820, 0.000, 0.310],  # Db
        [0.851, 0.000, 0.271],  # Sg
        [0.878, 0.000, 0.220],  # Bh
        [0.902, 0.000, 0.180],  # Hs
        [0.922, 0.000, 0.149],  # Mt
    ]
)

atomColors = atomColors.astype(int)

# https://www.schoolmykids.com/learn/interactive-periodic-table/covalent-radius-of-all-the-elements
# TODO: find potentially better source?
default = 0.5
covalentRadii = np.array(
    [
        default,
        0.37,
        0.32,
        1.34,
        0.9,
        0.82,
        0.77,
        0.75,
        0.73,
        0.71,
        0.69,
        1.54,
        1.3,
        1.18,
        1.11,
        1.06,
        1.02,
        0.99,
        0.97,
        1.96,
        1.74,
        1.44,
        1.36,
        1.25,
        1.27,
        1.39,
        1.25,
        1.26,
        1.21,
        1.38,
        1.31,
        1.26,
        1.22,
        1.19,
        1.16,
        1.14,
        1.1,
        2.11,
        1.92,
        1.62,
        1.48,
        1.37,
        1.45,
        1.56,
        1.26,
        1.35,
        1.31,
        1.53,
        1.48,
        1.44,
        1.41,
        1.38,
        1.35,
        1.33,
        1.3,
        2.25,
        1.98,
        1.69,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        1.6,
        1.5,
        1.38,
        1.46,
        1.59,
        1.28,
        1.37,
        1.28,
        1.44,
        1.49,
        1.48,
        1.47,
        1.46,
        default,
        default,
        1.45,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
        default,
    ]
)

covalentBonds = covalentRadii.reshape((-1, 1)) + covalentRadii.reshape((1, -1))

zStrToZInt = {
    "All": 0,
    "H": 1,
    "He": 2,
    "Li": 3,
    "Be": 4,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "Ne": 10,
    "Na": 11,
    "Mg": 12,
    "Al": 13,
    "Si": 14,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Ar": 18,
    "K": 19,
    "Ca": 20,
    "Sc": 21,
    "Ti": 22,
    "V": 23,
    "Cr": 24,
    "Mn": 25,
    "Fe": 26,
    "Co": 27,
    "Ni": 28,
    "Cu": 29,
    "Zn": 30,
    "Ga": 31,
    "Ge": 32,
    "As": 33,
    "Se": 34,
    "Br": 35,
    "Kr": 36,
    "Rb": 37,
    "Sr": 38,
    "Y": 39,
    "Zr": 40,
    "Nb": 41,
    "Mo": 42,
    "Tc": 43,
    "Ru": 44,
    "Rh": 45,
    "Pd": 46,
    "Ag": 47,
    "Cd": 48,
    "In": 49,
    "Sn": 50,
    "Sb": 51,
    "Te": 52,
    "I": 53,
    "Xe": 54,
    "Cs": 55,
    "Ba": 56,
    "La": 57,
    "Ce": 58,
    "Pr": 59,
    "Nd": 60,
    "Pm": 61,
    "Sm": 62,
    "Eu": 63,
    "Gd": 64,
    "Tb": 65,
    "Dy": 66,
    "Ho": 67,
    "Er": 68,
    "Tm": 69,
    "Yb": 70,
    "Lu": 71,
    "Hf": 72,
    "Ta": 73,
    "W": 74,
    "Re": 75,
    "Os": 76,
    "Ir": 77,
    "Pt": 78,
    "Au": 79,
    "Hg": 80,
    "Tl": 81,
    "Pb": 82,
    "Bi": 83,
    "Po": 84,
    "At": 85,
    "Rn": 86,
    "Fr": 87,
    "Ra": 88,
    "Ac": 89,
    "Th": 90,
    "Pa": 91,
    "U": 92,
    "Np": 93,
    "Pu": 94,
    "Am": 95,
    "Cm": 96,
    "Bk": 97,
    "Cf": 98,
    "Es": 99,
    "Fm": 100,
    "Md": 101,
    "No": 102,
    "Lr": 103,
    "Rf": 104,
    "Db": 105,
    "Sg": 106,
    "Bh": 107,
    "Hs": 108,
    "Mt": 109,
    "Ds": 110,
    "Rg": 111,
    "Cn": 112,
    "Uuq": 114,
    "Uuh": 116,
}

zIntToZStr = {v: k for k, v in zStrToZInt.items()}
