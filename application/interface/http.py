import json

from twisted.internet import reactor
from twisted.application import service
from twisted.web.http import HTTPChannel, Request, HTTPFactory

from nx.viper.interface import AbstractApplicationInterfaceProtocol


class HTTPRequest(AbstractApplicationInterfaceProtocol, Request):
    def process(self):
        reactor.callInThread(self.parseRequest)

    def parseRequest(self):
        """Parse request received."""
        requestUri = self.path.decode()
        segmentsUri = requestUri.split("/")

        # validating URI
        if len(segmentsUri) != 3:
            self.failRequestWithErrors(["InvalidRequestUri"])
            return

        # request version
        try:
            requestVersion = float(segmentsUri[1])
        except ValueError:
            self.failRequestWithErrors(["InvalidRequestVersion"])
            return

        # request method
        requestMethod = segmentsUri[2]

        # request parameters
        requestParameters = {}
        if (b"parameters" in self.args):
            try:
                requestParameters = json.loads(
                    self.args[b"parameters"][0].decode()
                )
            except json.JSONDecodeError:
                self.failRequestWithErrors(["InvalidParametersFormat"])
                return

        # creating request payload
        requestPayload = {}
        requestPayload["version"] = requestVersion
        requestPayload["method"] = requestMethod
        requestPayload["parameters"] = requestParameters

        self.channel.application.requestDispatcher.dispatch(
            self,
            requestPayload
        )

    # AbstractApplicationInterfaceProtocol
    def getIPAddress(self):
        return self.getClientIP()

    def requestPassedDispatcherValidation(self):
        # method is called before request is passed to controller
        pass

    def failRequestWithErrors(self, errors):
        self.requestResponse["code"] = 400
        self.requestResponse["content"] = None
        self.requestResponse["errors"] += errors

        self.sendFinalRequestResponse()

    def sendPartialRequestResponse(self):
        # HTTP does not actually support partial response
        pass

    def sendFinalRequestResponse(self):
        def sendResponse():
            # sending response and closing connection
            self.setResponseCode(200, "OK".encode())
            self.setHeader("Content-Type", "application/json")
            self.write(json.dumps(
                self.requestResponse,
                sort_keys=True
            ).encode())

            self.finish()

            # clearing response
            self.requestResponse["code"] = 200
            self.requestResponse["content"] = None
            self.requestResponse["errors"] = []

        reactor.callFromThread(sendResponse)


class HTTPProtocol(HTTPChannel):
    requestFactory = HTTPRequest

    def timeoutConnection(self):
        # preventing writing to log that a connection has been timed out as this is not an unusual issue (KeepAlive)
        pass


class HTTPFactory(HTTPFactory):
    def buildProtocol(self, addr):
        protocol = HTTPProtocol()
        protocol.application = self.application
        protocol.setTimeout(self.timeout)

        return protocol


class Service(service.Service):
    def __init__(self, application):
        self.application = application

    def startService(self):
        # creating HTTP
        httpFactory = HTTPFactory()
        httpFactory.application = self.application
        httpFactory.timeout = (
            self.application.config["interface"]["http"]["connection"]["timeout"]
        )

        self._reactor = reactor.listenTCP(
            self.application.config["interface"]["http"]["default"]["port"],
            httpFactory
        )

    def stopService(self):
        return self._reactor.stopListening()
