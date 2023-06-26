from client.environment import startHeadlessEnvironment

env = startHeadlessEnvironment()

dpath = "private/ethanol_spl_100.npz"
mpath = "private/ethanol_def_1000.npz"

env.taskLoadDataset(dpath, "sGDML")
env.taskLoadModel(mpath, "sGDML")

env.waitForTasks(verbose=True)

d = env.getDatasetFromPath(dpath)
m = env.getModelFromPath(mpath)

env.addToGenerationQueue("forcesError", model=m, dataset=d)
env.waitForTasks(verbose=True)

de = env.getData("forcesError", model=m, dataset=d)
print(de.get().shape)

env.save("ethData")

env.headlessQuit()
