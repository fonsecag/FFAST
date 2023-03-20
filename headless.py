from client.environment import runHeadless
from Utils.misc import setupLogger


async def main(env):
    # m1path, m2path = "private/neq_stachyose_1000.pth", "private/neq_DHA_1000.pth"
    # env.taskLoadModel(m1path)
    # env.taskLoadModel(m2path)

    d1path, d2path = "private/stach_2000.npz", "private/DHA_2000.npz"
    env.taskLoadDataset(d1path)
    env.taskLoadDataset(d2path)
    await env.waitForTasks()

    # m1 = env.getKeyFromPath(m1path)
    # m2 = env.getKeyFromPath(m2path)
    d1 = env.getKeyFromPath(d1path)
    d2 = env.getKeyFromPath(d2path)

    # env.addToGenerationQueue("forces", model=m1, dataset=d1)
    # env.addToGenerationQueue("forces", model=m2, dataset=d2)

    for dataset in env.getAllDatasetKeys():
        env.addToGenerationQueue("datasetCluster", model=None, dataset=dataset)

    await env.waitForTasks(verbose=True)
    env.save("savetest")


if __name__ == "__main__":
    setupLogger()
    runHeadless(main)
