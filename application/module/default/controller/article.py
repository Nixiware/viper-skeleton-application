import datetime

from nx.viper.controller import Controller as ViperController


class Controller(ViperController):
    def preDispatch(self):
        """
        Optional method called before the action is dispatched.

        :return: <void>
        """
        self.articleModel = self.application.getModel("default.article")
        self.nestedService = self.application.getService("default.nestedService")

    def createAction(self):
        """
        Demo REST API method for creating a new article.

        * input validation
        * API versioning
        * response success handler
        * response fail handler

        :return: <void>
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

        # define success and fail callbacks
        def successCallback(articleID):
            self.responseCode = 200
            self.responseContent["articleID"] = articleID
            self.responseContent["serviceOutput"] = self.nestedService.performAction("articleCreate")
            self.sendFinalResponse()

        def failCallback():
            self.responseCode = 400
            self.sendFinalResponse()

        if self.requestVersion == 1.1:
            # perform article creation
            self.articleModel.createArticle(
                successCallback,
                failCallback,
                title=self.requestParameters["title"],
                date=datetime.datetime.utcnow(),
                ip=self.requestProtocol.getIPAddress()
            )
        else:
            failCallback()

    def postDispatch(self):
        """
        Optional method called after the action is dispatched.

        :return:
        """
        pass
