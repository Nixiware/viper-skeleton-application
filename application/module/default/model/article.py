from twisted.internet import reactor


class Model:
    application = None
    dbService = None

    def __init__(self, application):
        self.application = application
        self.dbService = self.application.getService("viper.database")

    def createArticle(self, successHandler=None, failHandler=None, **kwargs):
        """
        Creates a new article in persistent storage.

        :param successHandler: <function(<int>)> method called if action is completed successfully with the first
                                argument being the newly created article's ID
        :param failHandler: <function(<str>)> method called if action fails with the first argument being the error
                                message
        :param kwargs:
            :param tableColumnName: <string/int> value for column in persistent storage

        :return: <void>
        """
        def createCallback(transaction, successHandler, failHandler, **kwargs):
            # create query
            queryInsert = "INSERT INTO `article_article` ("
            if len(kwargs) > 0:
                count = 0
                for key, value in kwargs.items():
                    queryInsert = "{}`{}`".format(queryInsert, key)

                    if count != len(kwargs) - 1:
                        queryInsert = "{}, ".format(queryInsert)
                    count += 1
            else:
                if failHandler is not None:
                    reactor.callInThread(failHandler)

            # add parameters from kwargs
            queryInsert = "{}) VALUES (".format(queryInsert)
            queryInsertParams = []
            count = 0
            for key, value in kwargs.items():
                if value is not None:
                    queryInsert = "{}%s".format(queryInsert, key)
                    queryInsertParams.append(value)
                else:
                    queryInsert = "{}NULL ".format(queryInsert, key)

                if count != len(kwargs) - 1:
                    queryInsert = "{}, ".format(queryInsert)
                count += 1

            # finishing the query
            queryInsert = "{});".format(queryInsert)

            try:
                # executing insert
                transaction.execute(
                    queryInsert,
                    tuple(queryInsertParams)
                )

                # getting newly inserted article ID
                articleID = None
                transaction.execute(
                    "SELECT LAST_INSERT_ID() FROM article_article LIMIT 1;"
                )
                results = list(transaction.fetchall())

                if len(results) == 1 and len(results[0]) and isinstance(results[0][0], int):
                    articleID = results[0][0]
            except Exception as e:
                if failHandler is not None:
                    reactor.callInThread(failHandler, str(e))

                return

            if successHandler is not None:
                reactor.callInThread(successHandler, articleID)

        try:
            self.dbService.runInteraction(createCallback, successHandler, failHandler, **kwargs)
        except Exception as e:
            if failHandler is not None:
                reactor.callInThread(failHandler, str(e))
