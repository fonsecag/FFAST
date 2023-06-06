from client.environment import runHeadless
from utils import setupLogger

async def main(env):
    # m1path, m2path = "private/neq_stachyose_1000.pth", "private/neq_DHA_1000.pth"
    # env.taskLoadModel(m1path)
    # env.taskLoadModel(m2path)


    d1path, d2path = "private/md22_DHA.npz", "private/md22_stachyose.npz"
    env.taskLoadDataset(d1path, "sGDML")
    env.taskLoadDataset(d2path, "sGDML")
    await env.waitForTasks()

    d1 = env.getDataset(env.getKeyFromPath(d1path))
    d2 = env.getDataset(env.getKeyFromPath(d2path))

    env.taskLoad("private/saves/Neq")
    env.taskLoad("private/saves/MACE")

    await env.waitForTasks()


    m1, m2, m3 = None, None, None
    for x in env.getAllModels():
        if x.getName() == "Nequip Stachyose":
            m2 = x
        elif x.getName() == "Nequip DHA":
            m1 = x
        elif x.getName() == "mace_DHA_1000":
            m3 = x
        elif x.getName() == "mace_stachyose_1000":
            m4 = x


    env.addToGenerationQueue("atomicForcesError", model=m4, dataset=d2)
    env.addToGenerationQueue("atomicForcesError", model=m2, dataset=d2)
    # env.addToGenerationQueue("atomicForcesError", model=m1, dataset=d1)
    # env.addToGenerationQueue("atomicForcesError", model=m2, dataset=d2)
    await env.waitForTasks(verbose=True)

    
    deNeq = env.getData("atomicForcesError", model=m2, dataset=d2)
    deMace = env.getData("atomicForcesError", model=m4, dataset=d2)

    env.startInteract(**locals())


    # for dataset in env.getAllDatasetKeys():
        # env.addToGenerationQueue("datasetCluster", model=None, dataset=dataset)

    await env.waitForTasks(verbose=True)
    # env.save("savetest")


if __name__ == "__main__":
    setupLogger()
    runHeadless(main)
