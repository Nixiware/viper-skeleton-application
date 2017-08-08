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
        pass

    def failRequestWithErrors(self, errors):
        self.requestResponse["code"] = 400
        self.requestResponse["errors"] += errors

        self.sendFinalRequestResponse()

    def sendPartialRequestResponse(self):
        pass

    def sendFinalRequestResponse(self):
        def sendResponse():
            self.setResponseCode(200, "OK".encode())
            self.setHeader("Content-Type", "application/json")
            self.write(json.dumps(
                self.requestResponse,
                sort_keys=True
            ).encode())

            self.finish()
            self.transport.loseConnection()

        reactor.callFromThread(sendResponse)


class HTTPProtocol(HTTPChannel):
    requestFactory = HTTPRequest


class HTTPFactory(HTTPFactory):
    def buildProtocol(self, addr):
        protocol = HTTPProtocol()
        protocol.application = self.application
        protocol.timeOut = self.timeout

        return protocol


class Service(service.Service):
    def __init__(self, application):
        self.application = application

    def startService(self):
        factory = HTTPFactory()
        factory.application = self.application
        factory.timeout = (
            self.application.config["interface"]["http"]["timeout"]
        )

        self._reactor = reactor.listenTCP(
            self.application.config["interface"]["http"]["port"],
            factory
        )

    def stopService(self):
        return self._reactor.stopListening()
