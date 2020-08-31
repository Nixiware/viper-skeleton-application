import datetime

from nx.viper.controller import Controller as ViperController


class Controller(ViperController):
    """
    Basic CRUD example.

    * input validation
    * API versioning
    * responding successfully
    * handling failures
    """

    def preDispatch(self):
        """
        Optional method called before the action is dispatched.

        :return: <void>
        """
        self.articleService = self.application.getService("default.article")
        self.nestedService = self.application.getService("default.nestedService")

    def createAction(self):
        """
        Create new article in persistent storage.

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
            self.responseContent["article_id"] = articleID

            # example of accessing module service, getting data from it, and showing response
            self.responseContent["serviceOutput"] = self.nestedService.performAction("articleCreate")

            self.sendFinalResponse()

        def failCallback(errors):
            self.responseCode = 400
            self.responseErrors.extend(errors)
            self.sendFinalResponse()

        # checking request version
        if self.requestVersion == 1.1:
            # perform article creation
            self.articleService.create(
                successCallback,
                failCallback,
                title=self.requestParameters["title"],
                date=datetime.datetime.utcnow(),
                ip=self.requestProtocol.getIPAddress()
            )
        else:
            failCallback(["UnsupportedRequestVersion"])

    def getAction(self):
        """
        Read article from persistent storage.

        :return: <void>
        """
        isValid = True
        if "article_id" not in self.requestParameters:
            isValid = False
            self.responseErrors.append("article_id.IsEmpty")
        elif not isinstance(self.requestParameters["article_id"], int):
            isValid = False
            self.responseErrors.append("article_id.NotInt")

        if not isValid:
            self.responseCode = 400
            self.responseContent = None
            self.sendFinalResponse()
            return

        def successCallback(article):
            self.responseCode = 200
            self.responseContent["article"] = {
                "article_id": article.identifier,
                "title": article.title,
                "date": article.date.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.sendFinalResponse()

        def failCallback(errors):
            if "ArticleNotFound" in errors:
                self.responseCode = 404
            else:
                self.responseCode = 400
            self.responseErrors.extend(errors)
            self.sendFinalResponse()

        self.articleService.get(
            ("article_id", "=", self.requestParameters["article_id"]),
            successCallback,
            failCallback
        )

    def updateAction(self):
        """
        Update existing article from persistent storage.

        :return: <void>
        """
        # performing input validation
        isValid = True
        if "article_id" not in self.requestParameters:
            isValid = False
            self.responseErrors.append("article_id.IsEmpty")
        elif not isinstance(self.requestParameters["article_id"], int):
            isValid = False
            self.responseErrors.append("article_id.NotInt")

        if "title" not in self.requestParameters:
            isValid = False
            self.responseErrors.append("title.IsEmpty")
        elif not isinstance(self.requestParameters["title"], str):
            isValid = False
            self.responseErrors.append("title.NotString")

        if not isValid:
            self.responseCode = 400
            self.responseContent = None
            self.sendFinalResponse()
            return

        def successCallback():
            self.responseCode = 200
            self.sendFinalResponse()

        def failCallback(errors):
            self.responseCode = 400
            self.responseErrors.extend(errors)
            self.sendFinalResponse()

        def updateCallback(article):
            self.articleService.update(
                ("article_id", "=", self.requestParameters["article_id"]),
                successCallback,
                failCallback,
                title=self.requestParameters["title"]
            )

        # checking if article exists before performing update
        self.articleService.get(
            ("article_id", "=", self.requestParameters["article_id"]),
            updateCallback,
            failCallback
        )

    def deleteAction(self):
        """
        Delete existing article from persistent storage.

        :return:
        """
        isValid = True
        if "article_id" not in self.requestParameters:
            isValid = False
            self.responseErrors.append("article_id.IsEmpty")
        elif not isinstance(self.requestParameters["article_id"], int):
            isValid = False
            self.responseErrors.append("article_id.NotInt")

        if not isValid:
            self.responseCode = 400
            self.responseContent = None
            self.sendFinalResponse()
            return

        def successCallback():
            self.responseCode = 200
            self.sendFinalResponse()

        def failCallback(errors):
            self.responseCode = 400
            self.responseErrors.extend(errors)
            self.sendFinalResponse()

        def deleteCallback(article):
            self.articleService.delete(
                ("article_id", "=", self.requestParameters["article_id"]),
                successCallback,
                failCallback
            )

        # checking if article exists before deletion
        self.articleService.get(
            ("article_id", "=", self.requestParameters["article_id"]),
            deleteCallback,
            failCallback
        )

    def postDispatch(self):
        """
        Optional method called after the action is dispatched.

        :return:
        """
        pass
