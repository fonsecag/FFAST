import numpy as np
from scipy.spatial.transform import Rotation


def getVV0Angle(v, v0, directionVector=None):
    u, u0 = v / np.linalg.norm(v), v0 / np.linalg.norm(v0)
    if directionVector is None:
        sign = 1
    else:
        cross = np.cross(v, v0)
        sign = -np.sign(np.dot(directionVector, cross))
    return sign * np.arccos(np.dot(u, u0))


def getVV0RotationMatrix(v, v0):

    vPerp = np.cross(v, v0)
    vPerp /= np.linalg.norm(vPerp)
    angle = getVV0Angle(v, v0)

    rotMatrix = Rotation.from_rotvec(-angle * vPerp)

    return rotMatrix.as_matrix()


def getPerpComponent(v, vRef, unitary=False):
    vPar = np.dot(v, vRef) * vRef
    vPerp = v - vPar
    if unitary:
        vPerp /= np.linalg.norm(v)

    return vPerp


def alignConfiguration(r, r0, along=[0, 1, 2], com=False):
    n1, n2, n3 = along

    # translate to overlap first atom
    d = r0[n1] - r[n1]
    r += d

    # align v12
    rotMatrix = getVV0RotationMatrix(r[n2] - r[n1], r0[n2] - r0[n1])

    # change origin, will be changed back later by aligning center of mass f.e.
    r -= r0[n1]
    r = np.matmul(r, rotMatrix)

    # rotate around v12 to align third atom
    v12 = r[n2] - r[n1]
    u12 = v12 / np.linalg.norm(v12)
    vpp = getPerpComponent(
        r[n3], u12, unitary=True
    )  # remember that r[n1] is origin atm
    vpp0 = getPerpComponent(r0[n3] - r0[n1], u12, unitary=True)
    angle = getVV0Angle(vpp, vpp0, directionVector=u12)
    rotMatrix = Rotation.from_rotvec(angle * u12).as_matrix()
    r = np.matmul(r, rotMatrix)

    if com:
        # align center of mass
        d = np.mean(r0[along], axis=0) - np.mean(r[along], axis=0)
        r += d
    else:
        # change back origin
        r += r0[n1]

    return r
