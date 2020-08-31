class Article:
    def __init__(self, identifier, title, date, ip):
        self._identifier = identifier
        self._title = title
        self._date = date
        self._ip = ip

    @property
    def identifier(self):
        return self._identifier

    @identifier.setter
    def identifier(self, value):
        self._identifier = value

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, value):
        self._date = value

    @property
    def ip(self):
        return self._ip

    @date.setter
    def ip(self, value):
        self._ip = value

    def toDictionary(self):
        """
        Output Article's data into a serializable dictionary.

        :return: <dict>
        """
        return {
            "article_id": self._identifier,
            "title": self._title,
            "date": self._date,
            "ip": self._ip
        }

    @staticmethod
    def fromDictionary(dict):
        """
        Create Article from dictionary.

        :param dict: <dict>
        :return: Article
        """
        return Article(
            identifier=dict["article_id"],
            title=dict["title"],
            date=dict["date"],
            ip=dict["ip"]
        )
