from client.environment import runHeadless
import asyncio

async def main(env):

    env.taskLoadDataset("private/ethanol.npz")
    env.taskLoadDataset("private/ethanol_spl_200.npz")

    env.taskLoadModel("private/ethanol_def_1000.npz")
    env.taskLoadModel("private/eth_il_1000.npz")

    await env.waitForTasks()

    for model in env.getAllModelKeys():
        for dataset in env.getAllDatasetKeys():
            env.addToGenerationQueue("forces",model=model, dataset=dataset)
            
    await env.waitForTasks()

runHeadless(main)
