from events import EventClass
import asyncio
import logging
import queue
import asyncio

logger = logging.getLogger("FFAST")


class TaskManager(EventClass):
    """
    The TaskManager class is responsible for (you guessed it) managing tasks.
    All tasks are run either asynchronously so as to not interrupt the
    execution of the main UI loop or other tasks. Some heavier tasks can also
    be run in a separate process (NYI).

    The task manager will automatically inform eventclasses (i.e. the UI) when
    a task is started and completed, though continuous progress updates must
    be provided in the worker functions themselves (via "TASK_PROGRESS" events)
    """

    latestTaskID = 0

    def __init__(self):
        super().__init__()

        self.runningTasks = {}
        self.taskQueue = queue.SimpleQueue()

        self.eventSubscribe("TASK_DONE", self.onTaskDone)
        self.eventSubscribe("QUIT_EVENT", self.quit, asynchronous=True)
        self.eventSubscribe("TASK_CANCEL", self.cancelTask, asynchronous=True)
        self.eventSubscribe(
            "TASK_PROGRESS", self.setTaskProgress, asynchronous=True
        )

    async def quit(self):
        tasks = []
        for (k, v) in self.runningTasks.items():
            await self.cancelTask(k)
            tasks.append(v["task"])

        self.eventPush("QUIT_READY")

    def onTaskDone(self, taskID):
        if taskID in self.runningTasks:
            del self.runningTasks[taskID]

    async def cancelTask(self, taskID):
        task = self.getTask(taskID)
        if task is None:
            return

        logger.info(f"Cancelling task {taskID} with name {task['name']}")
        task["task"].cancel()

        try:
            await task["task"]
        except asyncio.CancelledError:
            logger.info(f"Successfully cancelled task {taskID}")
            self.eventPush(
                "TASK_DONE", taskID
            )  # makes sure it gets removed from UI

    def getTask(self, taskID):
        return self.runningTasks.get(taskID, None)

    def isTaskRunning(self, taskID):
        return taskID in self.runningTasks

    def newTask(
        self,
        func,
        args=None,
        kwargs=None,
        visual=False,
        name="?",
        threaded=False,
        taskKey=None,
        componentParent=None,
    ):
        # TODO review doc
        """
        Bread and butter method of the TaskManager. Used whenever a background
        task should be completed without interrupting the main flow of the UI.
        Communication with the UI is done via events, which need to be called
        manually by the function passed to the method.

        Args:
            func (function): Function to be completed during task. Needs to be
                asynchronous and should acceptan optional taskID kwarg.
            args (iterable, optional): Arguments to be passed to the function.
                Defaults to None.
            kwargs (dict, optional): Keyword arguments to be passed to the
                function. Defaults to None.
            visual (bool, optional): Flag controlling whether the task should
                be displayed in the UI. Defaults to False.
            threaded (bool, optional): Flag controlling whether the task should
                be run in a different thread. Use for IO-bound blocking tasks
                (such as loading large datasets). Defaults to False.
        """

        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        if taskKey is not None:
            taskID = taskKey
        else:
            self.latestTaskID += 1
            taskID = self.latestTaskID

        if taskID in self.runningTasks:
            logger.info(
                f"Tried running task with key/id {taskID}, but task"
                " with that key/id is already running."
            )
            return

        taskInfo = {
            "visual": visual,
            "process": False,  # not yet used
            "name": name,
            "threaded": threaded,
            "progress": None,
            "progressMessage": "N/A",
        }

        loop = asyncio.get_event_loop()

        if threaded:
            co = asyncio.to_thread(func, *args, **kwargs, taskID=taskID)

            async def taskWrapper(c0, taskID):
                await co
                self.eventPush("TASK_DONE", taskID)

            task = loop.create_task(taskWrapper(co, taskID))
            taskInfo["coroutine"] = co
        else:

            async def taskWrapper(args, kwargs, taskID):
                await func(*args, **kwargs, taskID=taskID)
                self.eventPush("TASK_DONE", taskID)

            task = loop.create_task(taskWrapper(args, kwargs, taskID))

        taskInfo["task"] = task
        taskInfo["componentParent"] = componentParent
        taskInfo["taskID"] = taskID

        task.taskID = taskID
        task.add_done_callback(self.handleTaskResult)

        self.runningTasks[taskID] = taskInfo

        self.eventPush("TASK_CREATED", taskID)

    def handleTaskResult(self, task):

        # https://quantlane.com/blog/ensure-asyncio-task-exceptions-get-logged/
        try:
            task.result()

        except asyncio.CancelledError:
            pass  # Task cancellation should not be logged as an error.

        except Exception:  # pylint: disable=broad-except
            logging.exception("Exception raised by task = %r", task)
            self.eventPush("TASK_DONE", task.taskID)

    def queueTask(self, *args, taskKey=None, **kwargs):
        if (taskKey is not None) and (taskKey in self.runningTasks):
            logger.debug(
                f"Tried queuing task with key/id {taskKey}, but task"
                " with that key/id is already running."
            )
            return
        kwargs["taskKey"] = taskKey
        self.taskQueue.put((args, kwargs))

    async def handleTaskQueue(self):
        q = self.taskQueue

        if q.empty():
            return

        args, kwargs = q.get()

        self.newTask(*args, **kwargs)

    async def setTaskProgress(
        self,
        taskID,
        progMax=None,
        prog=None,
        percent=False,
        message="Working...",
    ):
        task = self.getTask(taskID)
        if task is None:
            return

        if (progMax is not None) and (prog is not None):
            task["progress"] = prog / progMax
        else:
            task["progress"] = None

        task["progressMessage"] = message
