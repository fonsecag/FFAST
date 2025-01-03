import asyncio
import logging
import os
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from client.environment import Environment
from events import EventClass
from utils import loadModules, setupLogger


class NathHorthath(EventClass):
    """
    Purely for debugging/testing purposes
    """

    def __init__(self, env):
        super().__init__()
        self.env = env

    async def countingTask(self, taskID=None):
        for i in range(10):
            self.eventPush(
                "TASK_PROGRESS",
                taskID,
                progMax=20,
                prog=i,
                message="Counting a bit",
                quiet=True,
            )
            await asyncio.sleep(0.2)
            print(i)

        for i in range(10, 20):
            self.eventPush(
                "TASK_PROGRESS",
                taskID,
                progMax=20,
                prog=i,
                message="Counting some more",
                quiet=True,
            )
            await asyncio.sleep(0.2)
            print(i)

    async def predictTask(self, taskID=None):
        env = self.env

        while True:
            await asyncio.sleep(1)

            if (len(env.models) < 1) or (len(env.datasets) < 1):
                continue

            dataset = env.datasets[next(iter(env.datasets))]
            model = env.models[next(iter(env.models))]

            env.taskGenerateData(
                "energyError", model=model, dataset=dataset, visual=True
            )
            break

    async def taskWatchDog(self, taskID=None):
        while True:
            await asyncio.sleep(1)
            print(len(self.env.tm.runningTasks))


async def eventLoop(UI, env):
    nh = NathHorthath(env)
    taskManager = env.tm

    # Temporarily putting some preliminary tasks here
    if True and os.path.exists("private"):
        # env.taskLoadDataset("private/big.npz", "sGDML")
        # env.taskLoadDataset("private/myoglobin_1000.npz")
        # env.taskLoadDataset("private/ethanol_spl_200.npz", "sGDML")
        # env.taskLoadDataset("private/ethanol_spl_100.npz", "sGDML")
        # env.taskLoadDataset("private/grid.npz", "sGDML")
        # env.taskLoadDataset("private/DHA_1000.xyz", "ase")
        env.taskLoadDataset("private/AcAla3_1000.npz", "sGDML")
        env.taskLoadDataset("private/AcPhe_2000.npz", "sGDML")
        # env.taskLoad("private/saves/MACE")
        # env.taskLoadDataset("private/unfolding_100.npz", "sGDML")
        # env.taskLoadDataset("private/unfolding.npz", "sGDML")
        # env.taskLoad("private/saves/unfolding")
        # env.taskLoadDataset("private/md22_stachyose.npz", "sGDML")
        # env.taskLoad("private/saves/MACE")
        # env.taskLoadModel("private/neq_DHA_1000.pth", "Nequip")
        # env.taskLoadModel("private/neq_sal_1000.pth")
        # env.taskLoadModel("private/ethanol_def_1000.npz", "sGDML")
        # env.taskLoadModel("private/eth_il_1000.npz", "sGDML")
        # env.taskLoadModel("private/eth_schnet", "SchNet")
        # env.loadZeroModel()

        # dpath = "private/train.npz"
        # # mpath = "private/maceIgor/MACE_tea_graphene_200_final_run-3_swa.model"
        # env.taskLoadDataset(dpath, "sGDML")
        # # env.taskLoadModel(mpath, "MACE")
        # env.taskLoad("maceGraphene")
        pass

    # env.newTask(nh.countingTask, name="TaskWatchDog", visual=True)
    while not UI.quitReady:
        await UI.eventHandle()
        await env.eventHandle()
        await nh.eventHandle()
        await env.handleGenerationQueue()
        await taskManager.eventHandle()
        await taskManager.handleTaskQueue()
        await asyncio.sleep(0.1)

    await UI.eventHandle()
    await env.eventHandle()
    await taskManager.eventHandle()
    await taskManager.quit()


def main():
    from UI.UIHandler import UIHandler

    app = QApplication(sys.argv)

    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    UI = UIHandler()
    UI.launch(app)

    env = Environment(headless=False)
    UI.setEnvironment(env)

    loadModules(UI, env)

    # await eventLoop(UI, env)
    event_loop.run_until_complete(eventLoop(UI, env))
    event_loop.close()


if __name__ == "__main__":
    # add logging filters
    class VispyNoiseFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return "QPyDesignerCustomWidgetCollection" not in msg

    vispyLogger = logging.getLogger("vispy")
    vispyLogger.addFilter(VispyNoiseFilter())

    mplLogger = logging.getLogger("matplotlib")
    mplLogger.setLevel(logging.WARN)

    setupLogger()
    logger = logging.getLogger("FFAST")

    try:
        main()
    except RuntimeError as e:
        if str(e) == "Event loop stopped before Future completed.":
            sys.exit()
        else:
            logger.error(e)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
        sys.exit()

    except Exception as e:
        logger.exception(e)
        sys.exit()
