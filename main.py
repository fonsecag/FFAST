import logging
from UI.base import UIHandler
from client.environment import Environment
import qasync
import asyncio
import sys
import time
import glob
import logging
import os
import importlib
from events import EventClass
from client.dataWatcher import DataWatcher
import vispy

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("debug.log"), logging.StreamHandler()],
)
logger = logging.getLogger("FFAST")


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
    if os.path.exists("private"):

        env.newTask(
            env.loadDataset,
            args=("private/ethanol.npz",),
            visual=True,
            name="Loading dataset",
            threaded=True,
        )

        env.newTask(
            env.loadDataset,
            args=("private/ethanol_spl_100.npz",),
            visual=True,
            name="Loading dataset",
            threaded=True,
        )

        env.newTask(
            env.loadModel,
            args=("private/eth_schnet",),
            visual=True,
            name="Loading model",
            threaded=True,
        )

        env.newTask(
            env.loadModel,
            args=("private/ethanol_def_1000.npz",),
            visual=True,
            name="Loading model",
            threaded=True,
        )

    # env.newTask(nh.taskWatchDog, name="TaskWatchDog", visual=True)

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


def loadModules(UI, env):
    for path in glob.glob(os.path.join("modules", "*.py")):
        name = os.path.basename(path).replace(".py", "")
        name = f"module_{name}"

        spec = importlib.util.spec_from_file_location(name, path)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)

        foo.load(UI, env)


async def main():
    UI = UIHandler()
    UI.launch()

    env = Environment()
    UI.setEnvironment(env)
    UI.loadUiElements()

    loadModules(UI, env)

    await eventLoop(UI, env)


if __name__ == "__main__":

    # add logging filters
    class VispyNoiseFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return "QPyDesignerCustomWidgetCollection" not in msg

    vispyLogger = logging.getLogger("vispy")
    vispyLogger.addFilter(VispyNoiseFilter())

    try:
        qasync.run(main())
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
