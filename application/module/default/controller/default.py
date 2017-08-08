import time, datetime

from nx.viper.controller import Controller as ViperController


class Controller(ViperController):
    def createAction(self):
        articleModel = self.application.getModel("default.article")

        def successCallback():
            self.responseCode = 200
            self.sendFinalResponse()

        def failCallback():
            self.responseCode = 400
            self.sendFinalResponse()

        articleModel.createArticle(
            self.requestParameters["title"],
            datetime.datetime.now(),
            self.requestProtocol.getIPAddress(),
            successCallback,
            failCallback
        )
