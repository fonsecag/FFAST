from client.environment import startHeadlessEnvironment
import numpy as np

env = startHeadlessEnvironment()

dpath = "private/maceIgor/train2.npz"
mpath = "private/maceIgor/MACE_tea_graphene_200_final_run-3_swa.model"

env.taskLoadDataset(dpath, "sGDML")
env.taskLoadModel(mpath, "MACE")

env.waitForTasks(verbose=True)

d = env.getDatasetFromPath(dpath)
m = env.getModelFromPath(mpath)

d.lattice = np.array(
    [[17.25837925, 8.62899692, 0], [0, 14.9458635, 0], [0, 0, 38.70524185]]
)
print(d.getLattice())

env.addToGenerationQueue("forces", model=m, dataset=d)
env.waitForTasks(verbose=True)

de = env.getData("forces", model=m, dataset=d)

env.save("maceGrapheneLattice")

env.headlessQuit()
