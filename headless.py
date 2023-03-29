from client.environment import runHeadless
from Utils.misc import setupLogger
import logging

async def main(env):

    
    # for i in range(1, 5 ):
    for i in range(1,5):
        # env.taskLoadModel(f'private/mace_sal_100_{i}.model')
        env.taskLoadModel(f'private/neq_sal_100_{i}.pth')
        await env.waitForTasks()
        # loading mace models in parallel is not great because of the hack

    d1path = "private/sal_2000.npz"
    env.taskLoadDataset(d1path)
    await env.waitForTasks()

    d1 = env.getKeyFromPath(d1path)
    # d2 = env.getKeyFromPath(d2path)

    for m in env.getAllModelKeys():
        env.addToGenerationQueue("forcesError", model=m, dataset=d1)

    await env.waitForTasks(verbose=True)
    env.save("savetest")


if __name__ == "__main__":
    setupLogger(logging.WARN)
    runHeadless(main)