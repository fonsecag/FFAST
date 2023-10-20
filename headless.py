from client.environment import startHeadlessEnvironment
import numpy as np

env = startHeadlessEnvironment()

dpath = "private/train.npz"
mpath = "private/MACE_tea_graphene_200_final_run-3_swa.model"

env.taskLoadDataset(dpath, "sGDML")
env.taskLoadModel(mpath, "MACE")

env.waitForTasks(verbose=True)

d = env.getDatasetFromPath(dpath)
m = env.getModelFromPath(mpath)

env.addToGenerationQueue("forces", model=m, dataset=d)
env.waitForTasks(verbose=True)

de = env.getData("forces", model=m, dataset=d)

env.save("maceGraphene")

env.headlessQuit()
