from client.environment import runHeadless
from Utils.misc import setupLogger


async def main(env):

    env.taskLoadModel("private/eth_il_1000.npz")
    # env.taskLoadModel("private/mace_sal_1000.model")
    await env.waitForTasks()

    key = env.getKeyFromPath("private/eth_il_1000.npz")
    
    for model in env.getAllModelKeys():
        for dataset in env.getAllDatasetKeys():
            env.addToGenerationQueue("forces", model=model, dataset=dataset)
            # env.addToGenerationQueue("energyErrorDist",model=model, dataset=dataset)

    await env.waitForTasks(verbose=True)
    env.save("savetest")


if __name__ == "__main__":
    setupLogger()
    runHeadless(main)
