from client.environment import runHeadless
import asyncio

async def main(env):

    env.taskLoadDataset("private/ethanol_spl_100.npz")
    env.taskLoadDataset("private/ethanol_spl_200.npz")

    env.taskLoadModel("private/ethanol_def_1000.npz")
    env.taskLoadModel("private/eth_il_1000.npz")

    await env.waitForTasks()

    print(list(env.dataTypes.keys()))

    sys.exit()

    for model in env.getAllModelKeys():
        for dataset in env.getAllDatasetKeys():
            env.addToGenerationQueue("forcesErrorDist",model=model, dataset=dataset)
            env.addToGenerationQueue("energyErrorDist",model=model, dataset=dataset)
            
    await env.waitForTasks(verbose = True)

    # env.save("savetest")

if __name__ == '__main__':
    runHeadless(main)
