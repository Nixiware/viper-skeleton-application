from time import sleep

from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from nx.viper.application import Application


class Service:
    log = Logger()

    def __init__(self, application):
        self.application = application

        # binding method to run when application completed startup process
        self.application.eventDispatcher.addObserver(
            Application.kEventApplicationStart,
            self._applicationStart
        )

        # binding method to run when the application is asked to close
        self.application.eventDispatcher.addObserver(
            Application.kEventApplicationStop,
            self._applicationStop
        )

    def _applicationStart(self, data):
        """
        Method called when application completed startup process.

        :param data: <object> event data object
        :return: <void>
        """
        self.pendingApplicationShutdown = False

        self.articleModel = self.application.getModel("default.article")
        self.mailService = self.application.getService("viper.mail")

        # creating a action running on a background thread with a frequency of 60 seconds
        self.recurringAction = LoopingCall(reactor.callInThread, self._recurringAction)
        self.recurringAction.start(60 * 1, True)

    def _applicationStop(self, data):
        """
        Method to run when the application is asked to close.

        :param data: <object> event data object
        :return: <void>
        """
        self.pendingApplicationShutdown = True

        try:
            if hasattr(self, "recurringAction") and self.recurringAction is not None:
                self.recurringAction.stop()
        except Exception:
            pass

    def _recurringAction(self):
        """
        Example of a time consuming recurring action.

        :return: <void>
        """
        # checking if an application shutdown is pending in order to prevent a time consuming task from running
        if self.pendingApplicationShutdown:
            return

        # performing time consuming task
        sleep(2.5)
        self.log.debug("[Default.Default] Recurring action ran.")
        sendMail = self.mailService.send(
            (
                "admin@example.com",
            ),
            "Recurring action ran",
            "Hello Admin<br /><br />" \
            "Recurring action ran successfully."
        )
