import json

from twisted.logger import Logger
from twisted.internet import reactor
from twisted.application import service
from twisted.web.http import HTTPChannel, Request, HTTPFactory
from twisted.protocols.policies import WrappingFactory, ThrottlingFactory, LimitConnectionsByPeer

from nx.viper.interface import AbstractApplicationInterfaceProtocol


class Throttler(ThrottlingFactory):
    """
    MonkeyPatch

    Twisted's ThrottlingFactory does not provide a method to override the automatic logging.
    """
    log = Logger()

    def buildProtocol(self, addr):
        if self.connectionCount == 0:
            if self.readLimit is not None:
                self.checkReadBandwidth()
            if self.writeLimit is not None:
                self.checkWriteBandwidth()

        if self.connectionCount < self.maxConnectionCount:
            self.connectionCount += 1
            return WrappingFactory.buildProtocol(self, addr)
        else:
            self.log.warn("[HTTP]: Started throttling connections. Reason: maximum connection count reached.")
            return None


class PeerConnectionLimiter(LimitConnectionsByPeer):
    """
    MonkeyPatch

    Twisted's LimitConnectionsByPeer handles IPv4Address/IPv6Address incorrectly which renders this policy unusable.
    """

    def buildProtocol(self, addr):
        peerHost = addr.host
        connectionCount = self.peerConnections.get(peerHost, 0)
        if connectionCount >= self.maxConnectionsPerPeer:
            return None
        self.peerConnections[peerHost] = connectionCount + 1
        return WrappingFactory.buildProtocol(self, addr)

    def unregisterProtocol(self, p):
        peerHost = p.getPeer().host
        self.peerConnections[peerHost] -= 1
        if self.peerConnections[peerHost] == 0:
            del self.peerConnections[peerHost]


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
        # validating configuration
        if self.application.config["interface"]["http"]["connection"]["maximum"] < self.application.config["interface"]["http"]["connection"]["maximumByPeer"]:
            raise ValueError("[HTTP]: You cannot set the total number of connections allowed lower than the total connections per peer.")

        # creating HTTP
        httpFactory = HTTPFactory()
        httpFactory.application = self.application
        httpFactory.timeout = (
            self.application.config["interface"]["http"]["connection"]["timeout"]
        )

        # enabling throttle settings
        httpThrottleFactory = Throttler(
            httpFactory,
            self.application.config["interface"]["http"]["connection"]["maximum"]
        )

        # enabling connection settings
        connectionLimitFactory = PeerConnectionLimiter(httpThrottleFactory)
        connectionLimitFactory.maxConnectionsPerPeer = self.application.config["interface"]["http"]["connection"]["maximumByPeer"]

        self._reactor = reactor.listenTCP(
            self.application.config["interface"]["http"]["default"]["port"],
            connectionLimitFactory
        )

    def stopService(self):
        return self._reactor.stopListening()
