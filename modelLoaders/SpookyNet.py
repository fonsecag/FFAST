from .loader import ModelLoader
import torch
from utils import md5FromArraysAndStrings
import numpy as np


class SpookyNetBatcher:
    def __init__(self, R, z, batchSize=50, cutoff=5):
        self.cutoff = cutoff

        N, nAtoms, _ = R.shape
        self.R = R
        self.Q = np.zeros(N)  # Charges, currently not really used
        self.S = np.zeros(N)  # Spin, idem
        z = np.repeat(z.reshape(1, -1), N, axis=0)
        self.z = torch.tensor(z, dtype=torch.int64, device="cpu")
        self.batchSize = batchSize
        self.nBatches = N // self.batchSize + 1
        self.nAtoms = nAtoms

        self.constructNeightboursList()

    def constructNeightboursList(self):
        # idx_i and idx_j
        # Why do they need to be given as args? Who the fuck knows
        N, nA, _ = self.R.shape
        cutoff = self.cutoff

        nidx_i, nidx_j, segs = [], [], []
        for i in range(N):
            i_batch = i % self.batchSize
            na_total_batch = i_batch * nA

            r = self.R[i]
            aidx_i, aidx_j = [], []

            for ai in range(nA):
                for aj in range(nA):
                    if ai == aj:
                        continue
                    d = np.linalg.norm(r[ai] - r[aj])
                    if d < cutoff:
                        aidx_i.append(int(ai + na_total_batch))
                        aidx_j.append(int(aj + na_total_batch))

            nidx_i.append(aidx_i)
            nidx_j.append(aidx_j)

            segs.append([i_batch] * nA)

        self.nidx_i = nidx_i
        self.nidx_j = nidx_j
        self.segs = np.array(segs)

    def batches(self, dump=False):
        N = self.R.shape[0]
        nBatches = self.nBatches
        if N % self.batchSize == 0:
            nBatches -= 1

        indices = np.arange(N)
        batchSize = self.batchSize
        if dump:
            nBatches = 1
            batchSize = self.R.shape[0]

        for i in range(nBatches):
            if i == N - 1:
                idx = indices[i * batchSize :]
            else:
                idx = indices[i * batchSize : (i + 1) * batchSize]

            R = torch.tensor(
                self.R[idx],
                dtype=torch.float32,
                device="cpu",
                requires_grad=True,
            )
            Q = torch.tensor(self.Q[idx], dtype=torch.float32, device="cpu")
            S = torch.tensor(self.S[idx], dtype=torch.float32, device="cpu")
            nidx_i = np.concatenate([self.nidx_i[x] for x in idx])
            nidx_j = np.concatenate([self.nidx_j[x] for x in idx])
            nidx_i = torch.tensor(nidx_i, dtype=torch.int64, device="cpu")
            nidx_j = torch.tensor(nidx_j, dtype=torch.int64, device="cpu")

            segs = torch.tensor(
                self.segs[idx], dtype=torch.int64, device="cpu"
            )
            Z = self.z[idx]

            yield {
                "R": R.reshape(-1, 3),
                "Z": Z.view(-1),
                "Q": Q.view(-1),
                "S": S.view(-1),
                "idx_i": nidx_i.view(-1),
                "idx_j": nidx_j.view(-1),
                "batch_seg": segs.view(-1),
                "num_batch": len(idx),
            }, idx

    def all(self):
        return next(self.batches(dump=True))


class SpookyNetModelLoader(ModelLoader):
    singlePredict = True
    modelName = "SpookyNet"

    def __init__(self, env, path):
        super().__init__(env, path)
        self.data = torch.load(path, map_location="cpu")
        self.cutoff = self.data["cutoff"]

        from spookynet.spookynet import SpookyNet

        self.model = SpookyNet(load_from=path).to(torch.float32).to("cpu")
        self.model.eval()

    def getFingerprint(self):
        from utils import md5FromArraysAndStrings

        lst = []
        for child in self.model.children():
            for param in child.parameters():
                lst.append(param.detach().numpy())

        fp = md5FromArraysAndStrings(*lst)
        return fp

    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        R = dataset.getCoordinates()
        if indices is not None:
            R = R[indices]

        batcher = SpookyNetBatcher(
            R, dataset.getElements(), batchSize=batchSize, cutoff=self.cutoff
        )

        E, F, i = [], [], 0
        for batch, idx in batcher.batches():
            res = self.model(
                **batch, use_forces=True, use_dipole=False, create_graph=False
            )
            e, f = res[0], res[1]

            E.append(e.detach().numpy())
            F.append(f.detach().numpy())
            i += 1

            if taskID is not None:
                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=batcher.nBatches,
                    prog=i,
                    message=f"SpookyNet batch predictions",
                    quiet=True,
                    percent=True,
                )

                if not self.env.tm.isTaskRunning(taskID):
                    return None

        E = np.concatenate(E, axis=0)
        F = np.concatenate(F, axis=0)

        return (E.flatten(), F.reshape(-1, batcher.nAtoms, 3))
