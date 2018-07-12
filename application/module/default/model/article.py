from datetime import datetime

from twisted.logger import Logger
from twisted.internet import reactor
from twisted.python.failure import Failure


class Model:
    log = Logger()

    def __init__(self, application):
        self.application = application
        self.dbService = self.application.getService("viper.database")

    def get(self, predicate, successHandler, failHandler=None):
        """
        Fetch article from persistent storage.

        :param predicate: <tuple> select condition consisting of: column name, relation, value
        :param successHandler: <function(<dict>)> method called if action is completed successfully where the first
                                argument is the article
        :param failHandler: <function(<list>)> method called if action fails where the first argument is a list of
                            error messages
        :return: <void>
        """
        querySelect = \
            "SELECT `article_id`, `title`, `date`, `ip` " \
            "FROM `article_article` " \
            "WHERE `{}` {} %s " \
            "LIMIT 1; ".format(
                predicate[0],
                predicate[1]
            )

        querySelectParams = []
        if isinstance(predicate[2], datetime):
            querySelectParams.append(predicate[2].strftime("%Y-%m-%d %H:%M:%S"))
        else:
            querySelectParams.append(predicate[2])

        def failCallback(error):
            errorMessage = str(error)
            if isinstance(error, Failure):
                errorMessage = error.getErrorMessage()

            self.log.error(
                "[Default.Article] get() database error: {errorMessage}",
                errorMessage=errorMessage
            )

            if failHandler is not None:
                reactor.callInThread(failHandler, ["DatabaseError"])

        def successCallback(results):
            if len(results) == 0 and failHandler is not None:
                reactor.callInThread(failHandler, ["ArticleNotFound"])
                return

            reactor.callInThread(successHandler, {
                "article_id": results[0][0],
                "title": results[0][1],
                "date": results[0][2],
                "ip": results[0][3]
            })

        operation = self.dbService.runQuery(
            querySelect,
            tuple(querySelectParams)
        )
        operation.addCallbacks(successCallback, failCallback)

    def create(self, successHandler=None, failHandler=None, **kwargs):
        """
        Create a new article in persistent storage.

        :param successHandler: <function(<int>)> method called if action is completed successfully where the first
                                argument is the newly created article's ID
        :param failHandler: <function(<list>)> method called if action fails where the first argument is a list of
                            error messages
        :param kwargs:
            :param tableColumnName: <string/datetime/int> value for column in persistent storage
        :return: <void>
        """
        def failCallback(error):
            errorMessage = str(error)
            if isinstance(error, Failure):
                errorMessage = error.getErrorMessage()

            self.log.error(
                "[Default.Article] create() database error: {errorMessage}",
                errorMessage=errorMessage
            )

            if failHandler is not None:
                reactor.callInThread(failHandler, ["DatabaseError"])

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
                failCallback(e)

                return

            if successHandler is not None:
                reactor.callInThread(successHandler, articleID)

        interaction = self.dbService.runInteraction(createCallback, successHandler, failHandler, **kwargs)
        interaction.addErrback(failCallback)

    def update(self, predicate, successHandler=None, failHandler=None, **kwargs):
        """
        Update existing article in persistent storage.

        :param predicate: <tuple> update condition consisting of: column name, relation, value
        :param successHandler: <function> method called if action is completed successfully
        :param failHandler: <function> method called if action fails where the first argument is a list of error
                            messages
        :param kwargs:
            :param tableColumnName: <string/datetime/int> value for column in persistent storage
        :return: <void>
        """
        queryUpdateParams = []
        queryUpdate = "UPDATE `article_article` SET "

        if len(kwargs) > 0:
            count = 0
            for key, value in kwargs.items():
                if value is not None:
                    queryUpdate = "{}`{}` = %s ".format(queryUpdate, key)

                    if isinstance(value, datetime):
                        queryUpdateParams.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                    else:
                        queryUpdateParams.append(value)
                else:
                    queryUpdate = "{}`{}` = NULL ".format(queryUpdate, key)

                if count != len(kwargs) - 1:
                    queryUpdate = "{}, ".format(queryUpdate)
                count += 1
        else:
            return

        queryUpdate = "{}WHERE `{}` {} %s LIMIT 1;".format(queryUpdate, predicate[0], predicate[1])
        queryUpdateParams.append(predicate[2])

        def failCallback(error):
            errorMessage = str(error)
            if isinstance(error, Failure):
                errorMessage = error.getErrorMessage()

            self.log.error(
                "[Default.Article] update() database error: {errorMessage}",
                errorMessage=errorMessage
            )

            if failHandler is not None:
                reactor.callInThread(failHandler, ["DatabaseError"])

        def successCallback(results):
            if successHandler is not None:
                reactor.callInThread(successHandler)

        operation = self.dbService.runOperation(
            queryUpdate,
            tuple(queryUpdateParams)
        )
        operation.addCallbacks(successCallback, failCallback)

    def delete(self, predicate, successHandler=None, failHandler=None):
        """
        Delete an existing article from persistent storage.

        :param predicate: delete condition consisting of: column name, relation, value
        :param successHandler: <function> method called if action is completed successfully
        :param failHandler: <function> method called if action fails where the first argument is a list of error
                            messages
        :return: <void>
        """
        queryDelete = "DELETE FROM `article_article` " \
                      "WHERE `{}` {} %s LIMIT 1;".format(
            predicate[0],
            predicate[1]
        )

        queryDeleteParams = []
        if isinstance(predicate[2], datetime):
            queryDeleteParams.append(predicate[2].strftime("%Y-%m-%d %H:%M:%S"))
        else:
            queryDeleteParams.append(predicate[2])

        def failCallback(error):
            errorMessage = str(error)
            if isinstance(error, Failure):
                errorMessage = error.getErrorMessage()

            self.log.error(
                "[Default.Article] delete() database error: {errorMessage}",
                errorMessage=errorMessage
            )

            if failHandler is not None:
                reactor.callInThread(failHandler, ["DatabaseError"])

        def successCallback(results):
            if successHandler is not None:
                reactor.callInThread(successHandler)

        operation = self.dbService.runOperation(
            queryDelete,
            tuple(queryDeleteParams)
        )
        operation.addCallbacks(successCallback, failCallback)
