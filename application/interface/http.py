import json

from zope.interface import directlyProvides, providedBy

from OpenSSL import crypto

from twisted.logger import Logger
from twisted.internet import reactor, ssl
from twisted.application import service
from twisted.web.http import HTTPChannel, Request, HTTPFactory
from twisted.protocols.policies import Protocol, ProtocolWrapper, WrappingFactory, ThrottlingFactory, LimitConnectionsByPeer, TimeoutFactory

from nx.viper.interface import AbstractApplicationInterfaceProtocol


class PatchedProtocolWrapper(ProtocolWrapper):
    """
    MonkeyPatch

    The HTTP interface implements multiple policies (Throttling, LimitConnectionsByPeer, Timeout)
    in order to keep the server resources in check and prevent DoS attacks.
    These policies are daisy chained around the HTTPFactory and the connection must pass each one
    before it reaches the HTTPFactory.
    Unfortunately if one of the policies cancels the connection, the rest of the chain is not notified.

    This worsens the situation because Twisted's ProtocolWrapper does not check if the wrappedProtocol
    actually exists, further polluting the log with unhandled exceptions.
    """
    def makeConnection(self, transport):
        directlyProvides(self, providedBy(transport))
        Protocol.makeConnection(self, transport)
        self.factory.registerProtocol(self)

        if self.wrappedProtocol is not None:
            self.wrappedProtocol.makeConnection(self)

    def dataReceived(self, data):
        if self.wrappedProtocol is not None:
            self.wrappedProtocol.dataReceived(data)

    def connectionLost(self, reason):
        self.factory.unregisterProtocol(self)
        if self.wrappedProtocol is not None:
            self.wrappedProtocol.connectionLost(reason)


# applying the patch for ProtocolWrapper
ProtocolWrapper.makeConnection = PatchedProtocolWrapper.makeConnection
ProtocolWrapper.dataReceived = PatchedProtocolWrapper.dataReceived
ProtocolWrapper.connectionLost = PatchedProtocolWrapper.connectionLost


class PatchedThrottlingFactory(ThrottlingFactory):
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


# applying the patch for ThrottlingFactory
ThrottlingFactory.log = Logger()
ThrottlingFactory.buildProtocol = PatchedThrottlingFactory.buildProtocol


class PatchedLimitConnectionsByPeer(LimitConnectionsByPeer):
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


# applying patch for LimitConnectionsByPeer
LimitConnectionsByPeer.buildProtocol = PatchedLimitConnectionsByPeer.buildProtocol
LimitConnectionsByPeer.unregisterProtocol = PatchedLimitConnectionsByPeer.unregisterProtocol


class HTTPRequest(AbstractApplicationInterfaceProtocol, Request):
    log = Logger()

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
        def clearResponseCallback():
            # clearing response
            self.requestResponse["code"] = 200
            self.requestResponse["content"] = None
            self.requestResponse["errors"] = []

        def sendResponseCallback():
            try:
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
            except Exception as e:
                self.log.debug("[HTTP]: Exception encountered while responding to request.")

            clearResponseCallback()

        # checking if any of the enabled policies closed the channel
        if self.channel is not None:
            reactor.callFromThread(sendResponseCallback)
        else:
            clearResponseCallback()


class HTTPProtocol(HTTPChannel):
    requestFactory = HTTPRequest

    def timeoutConnection(self):
        """
        Overriding HTTPChannel timeoutConnection to prevent logging pollution.

        If KeepAlive is used then every connection will be timed out at some point, which renders
        logging this event totally useless.

        Also by default the connection is not dropped when a timeout occurs, this method ensures
        that the request is completely cleared from the queue.
        """
        if self.abortTimeout is not None:
            # We use self.callLater because that's what TimeoutMixin does.
            self._abortingCall = self.callLater(
                self.abortTimeout, self.forceAbortClient
            )
        self.loseConnection()
        self.forceAbortClient()

    def forceAbortClient(self):
        """
        Overriding HTTPChannel forceAbortClient to prevent logging pollution.
        """
        self._abortingCall = None
        self.transport.abortConnection()


class HTTPFactory(HTTPFactory):
    def buildProtocol(self, addr):
        protocol = HTTPProtocol()
        protocol.application = self.application

        if self.keepAlive > 0:
            protocol.setTimeout(self.keepAlive)
        else:
            """
            According to Twisted's docs, in order to disable the timeout we need to set it to None.
            However setting it to None while using reactor.listenSSL reveals a bug where 
            subsequent requests are left in timeout.
            """
            protocol.setTimeout(0.1)

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

        # enabling timeout policy
        if self.application.config["interface"]["http"]["connection"]["timeout"] > 0:
            httpTimeoutFactory = TimeoutFactory(
                httpFactory,
                self.application.config["interface"]["http"]["connection"]["timeout"]
            )
        else:
            httpTimeoutFactory = httpFactory

        # enabling connection peer limit policy
        httpConnectionLimitFactory = LimitConnectionsByPeer(httpTimeoutFactory)
        httpConnectionLimitFactory.maxConnectionsPerPeer = self.application.config["interface"]["http"]["connection"]["maximumByPeer"]

        # enabling throttle policy
        httpThrottleFactory = ThrottlingFactory(
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
            # loading certificate
            certFile = open(self.application.config["interface"]["http"]["tls"]["certificatePath"], "rt")
            certData = certFile.read()
            certFile.close()
            certificate = crypto.load_certificate(crypto.FILETYPE_PEM, certData)

            # loading private key
            privateKeyFile = open(self.application.config["interface"]["http"]["tls"]["privateKeyPath"], "rt")
            privateKeyData = privateKeyFile.read()
            privateKeyFile.close()

            privateKeyPassphrase = None
            if len(self.application.config["interface"]["http"]["tls"]["privateKeyPassphrase"]) > 0:
                privateKeyPassphrase = self.application.config["interface"]["http"]["tls"]["privateKeyPassphrase"].encode()
            privateKey = crypto.load_privatekey(crypto.FILETYPE_PEM, privateKeyData, privateKeyPassphrase)

            # loading certificate chain
            certChain = []
            if len(self.application.config["interface"]["http"]["tls"]["certificateChainPaths"]) > 0:
                for chainPath in self.application.config["interface"]["http"]["tls"]["certificateChainPaths"]:
                    chainFile = open(chainPath, "rt")
                    chainData = chainFile.read()
                    chainFile.close()
                    certChain.append(crypto.load_certificate(crypto.FILETYPE_PEM, chainData))

            # creating the certificate options for reactor
            certificateOptions = ssl.CertificateOptions(
                certificate=certificate,
                privateKey=privateKey,
                extraCertChain=certChain
            )

            self._reactor = reactor.listenSSL(
                self.application.config["interface"]["http"]["tls"]["port"],
                httpThrottleFactory,
                certificateOptions,
                50
            )

    def stopService(self):
        return self._reactor.stopListening()
