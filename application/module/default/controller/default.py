import datetime

from nx.viper.controller import Controller as ViperController


class Controller(ViperController):
    def preDispatch(self):
        """Method is called (if defined) before the actual action is called."""
        self.articleModel = self.application.getModel("default.article")
        self.nestedService = self.application.getService("default.nestedService")

    def createAction(self):
        """
        Demo create article REST API method.

        * input validation
        * API versioning
        * response success handler
        * response fail handler
        """

        # performing input validation
        isValid = True
        if "title" not in self.requestParameters:
            isValid = False
            self.responseErrors.append("title.IsEmpty")
        elif not isinstance(self.requestParameters["title"], str):
            isValid = False
            self.responseErrors.append("title.NotString")

        # fail request if validation failed, and output errors
        if not isValid:
            self.responseCode = 400
            self.responseContent = None
            self.sendFinalResponse()
            return

        # define success & fail callbacks
        def successCallback():
            self.responseCode = 200
            self.responseContent["articleInsert"] = True
            self.responseContent["example"] = self.nestedService.performAction("test")
            self.sendFinalResponse()

        def failCallback():
            self.responseCode = 400
            self.sendFinalResponse()

        if self.requestVersion == 1.1:
            # perform article creation
            self.articleModel.createArticle(
                self.requestParameters["title"],
                datetime.datetime.now(),
                self.requestProtocol.getIPAddress(),
                successCallback,
                failCallback
            )
        else:
            failCallback()

    def postDispatch(self):
        """Method is called (if defined) after the actual action is called."""
        pass
