from client.environment import runHeadless
from Utils.misc import setupLogger


async def main(env):

    env.taskLoadDataset("private/salicylic_spookneq_train1000_val1000.npz")
    env.taskLoadModel("private/neq_sal_1000.pth")
    env.taskLoadModel("private/spook_sal_1000.pt")
    # env.taskLoadModel("private/mace_sal_1000.model")
    await env.waitForTasks()

    for model in env.getAllModelKeys():
        for dataset in env.getAllDatasetKeys():
            env.addToGenerationQueue("forces", model=model, dataset=dataset)
            # env.addToGenerationQueue("energyErrorDist",model=model, dataset=dataset)

    await env.waitForTasks(verbose=True)
    env.save("savetest")


if __name__ == "__main__":
    setupLogger()
    runHeadless(main)
