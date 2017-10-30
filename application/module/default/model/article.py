from twisted.internet import reactor


class Model:
    application = None
    dbService = None

    def __init__(self, application):
        self.application = application
        self.dbService = self.application.getService("viper.database")

    def createArticle(self,
                      title, date, ip,
                      successHandler=None, failHandler=None):
        createAction = self.dbService.runOperation(
            "INSERT INTO `article_article` (`article_id`, `title`, `date`, `ip`) "
            "VALUES (NULL, %s, %s, %s);",
            (title, date.strftime("%Y-%m-%d %H:%M:%S"), ip)
        )

        def success(_):
            if successHandler is not None:
                reactor.callInThread(successHandler)

        def fail(_):
            if failHandler is not None:
                reactor.callInThread(failHandler)

        createAction.addCallbacks(success, fail)
