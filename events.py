from collections import defaultdict
import logging, traceback
import os, time

logger = logging.getLogger("FFAST")
subs = defaultdict(list)

# WANTED TO MAKE THEM ONLY ABLE TO HAPPEN ONCE PER CYCLE
# FOR NOW IM STAGGERING INSIDE THE WIDGET REFRESH THINGY
# REFRESH_EVENTS = ["WIDGET_REFRESH", "WIDGET_VISUAL_REFRESH"]


def doNothing(*args):
    pass


class EventClass:
    """
    Main EventClass, to be inherited by any object that has an independent event loop (i.e. the UI Handler and the Environment).

    Gives access to subscribing, pushing and handling events.
    """

    isEventChild = False
    eventStamp = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eventQueue = []
        self.eventChildren = []
        self.subscribedTo = set()

    def eventSubscribe(self, event, func, asynchronous=False):
        """
        Subscribes to an event and provides the response function to be called.

        Args:
            event (str): Event name
            func (func): Function to me called when event happens
        """
        subs[event].append((self, func, asynchronous))
        self.subscribedTo.add(event)

    def eventPush(self, event, *args, quiet=False, **kwargs):
        """
        Pushes event onto the stack.

        Args:
            event (str): Event name
            quiet (bool, optional): Flag controlling whether the event should
                be included in logs. Set to True for quick-fire events such as
                TASK_PROGRESS. Defaults to False.
        """

        if not quiet:
            logger.debug(f"Event pushed: {event} by {type(self)}")

        for obj, func, asynchronous in subs[event]:
            obj.eventQueue.append(
                (event, func, asynchronous, quiet, args, kwargs)
            )

    eventBusy = None
    eventFree = None
    busy = False

    async def eventHandle(self):
        """
        Goes through the event queue, which includes every event pushed since
        last call, and calls the corresponding functions.

        This method needs to be called continously and regularly called,
        see main.py.
        """

        self.eventStamp += 1

        if (self.isEventChild) and (len(self.eventQueue) < 1):
            return

        self.busy = True
        if self.eventBusy is not None:
            self.eventPush(self.eventBusy)

        for event, func, asynchronous, quiet, args, kwargs in self.eventQueue:
            if not quiet:
                logger.debug(
                    f"{self} handling event {event}, function: {func}"
                )
            try:
                if asynchronous:
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except Exception:
                logger.exception(
                    f"Exception while {self} tried to handle event {event}.\nfunc:{func}\nargs:{args}\nkwargs:{kwargs}"
                )

        self.busy = False
        if self.eventFree is not None:
            self.eventPush(self.eventFree)

        self.eventQueue.clear()

        if not self.isEventChild:
            for child in self.eventChildren:
                await child.eventHandle()

    def addEventChild(self, obj):
        obj.eventParent = self
        self.eventChildren.append(obj)


class EventChildClass(EventClass):
    """
    EventClass for Qt Widgets, which cannot have an independent event handling loop. Instead, this class hooks onto the UI Handler and use its event handling methods instead.

    Note that after initialising the object, the parent needs to call addEventChild.
    """

    isEventChild = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if hasattr(self, "handler"):
            self.handler.addEventChild(self)

    def deleteEvents(self):
        # REMOVE IT FROM HANDLER'S EVENT CHILDREN
        eventChildren = self.eventParent.eventChildren
        eventChildren.remove(self)

        # REMOVE IT FROM SUBS
        for event in self.subscribedTo:
            eventSubs = subs[event]
            for i in range(len(eventSubs) - 1, -1, -1):
                if eventSubs[i][0] is self:
                    del eventSubs[i]

        self.deleteLater()
