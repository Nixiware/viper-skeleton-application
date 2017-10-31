import json

from twisted.logger import Logger
from twisted.internet import reactor, ssl
from twisted.application import service
from twisted.web.http import HTTPChannel, Request, HTTPFactory
from twisted.protocols.policies import WrappingFactory, ThrottlingFactory, LimitConnectionsByPeer, TimeoutFactory

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
        def sendResponseCallback():
            # sending response and closing connection
            self.setResponseCode(200, "OK".encode())
            self.setHeader("Content-Type", "application/json")
            self.write(json.dumps(
                self.requestResponse,
                sort_keys=True
            ).encode())

            # preparing request finish
            keepAlive = True
            if self.channel.application.config["interface"]["http"]["connection"]["keepAlive"] == 0:
                keepAlive = False

            self.finish()
            if not keepAlive:
                self.transport.loseConnection()

            # clearing response
            self.requestResponse["code"] = 200
            self.requestResponse["content"] = None
            self.requestResponse["errors"] = []

        # checking if any of the enabled policies closed the channel
        if self.channel is not None:
            reactor.callFromThread(sendResponseCallback)


class HTTPProtocol(HTTPChannel):
    requestFactory = HTTPRequest

    def timeoutConnection(self):
        """
        Overriding HTTPChannel timeoutConnection to prevent logging pollution.
        If KeepAlive is used then every connection will be timed out at some point, which renders logging this event totally useless.
        """
        if self.abortTimeout is not None:
            # We use self.callLater because that's what TimeoutMixin does.
            self._abortingCall = self.callLater(
                self.abortTimeout, self.forceAbortClient
            )
        self.loseConnection()


class HTTPFactory(HTTPFactory):
    def buildProtocol(self, addr):
        protocol = HTTPProtocol()
        protocol.application = self.application

        if self.keepAlive > 0:
            protocol.setTimeout(self.keepAlive)
        else:
            protocol.setTimeout(None)

        return protocol


class Service(service.Service):
    def __init__(self, application):
        self.application = application

    def startService(self):
        # validating configuration
        if self.application.config["interface"]["http"]["connection"]["maximum"] < self.application.config["interface"]["http"]["connection"]["maximumByPeer"]:
            raise ValueError("[HTTP]: You cannot set the total number of connections allowed lower than the total connections per peer.")

        # creating HTTP factory
        httpFactory = HTTPFactory()
        httpFactory.application = self.application
        httpFactory.keepAlive = (
            self.application.config["interface"]["http"]["connection"]["keepAlive"]
        )

        # enabling timeout settings
        if self.application.config["interface"]["http"]["connection"]["timeout"] > 0:
            httpTimeoutFactory = TimeoutFactory(
                httpFactory,
                self.application.config["interface"]["http"]["connection"]["timeout"]
            )
        else:
            httpTimeoutFactory = httpFactory

        # enabling connection settings
        httpConnectionLimitFactory = PeerConnectionLimiter(httpTimeoutFactory)
        httpConnectionLimitFactory.maxConnectionsPerPeer = self.application.config["interface"]["http"]["connection"]["maximumByPeer"]

        # enabling throttle settings
        httpThrottleFactory = Throttler(
            httpConnectionLimitFactory,
            self.application.config["interface"]["http"]["connection"]["maximum"]
        )

        # starting default (unsecure) http interface
        if self.application.config["interface"]["http"]["default"]["enabled"]:
            self._reactor = reactor.listenTCP(
                self.application.config["interface"]["http"]["default"]["port"],
                httpThrottleFactory,
                50
            )

        # starting TLS (secure) http interface
        if self.application.config["interface"]["http"]["tls"]["enabled"]:
            # loading certificate & private key
            pemFile = open(self.application.config["interface"]["http"]["tls"]["pem"], "rb")
            pemData = pemFile.read()
            pemFile.close()

            certificate = ssl.PrivateCertificate.loadPEM(pemData)

            self._reactor = reactor.listenSSL(
                self.application.config["interface"]["http"]["tls"]["port"],
                httpThrottleFactory,
                certificate.options(),
                50
            )

    def stopService(self):
        return self._reactor.stopListening()
