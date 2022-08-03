from events import EventClass
from tasks import TaskManager


class Client(EventClass):
    """
    Client class, handles requests sent from the UI or other. The client
    receives events that request calculations be made and passes the respective
    methods to the task manager.

    Every client is responsible for a single environment.
    """

    def __init__(self):
        super().__init__()
