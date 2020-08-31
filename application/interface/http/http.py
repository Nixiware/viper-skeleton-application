import hmac
import hashlib
import json
from calendar import timegm
from datetime import datetime

from OpenSSL import crypto

from twisted.logger import Logger
from twisted.internet import reactor, ssl
from twisted.application import service
from twisted.web.http import HTTPChannel, Request, HTTPFactory
from twisted.protocols.policies import ProtocolWrapper, ThrottlingFactory, LimitConnectionsByPeer, TimeoutFactory

from nx.viper.interface import AbstractApplicationInterfaceProtocol

from application.interface.http.policies import PatchedProtocolWrapper, PatchedThrottlingFactory, PatchedLimitConnectionsByPeer

# applying the patch for ProtocolWrapper
ProtocolWrapper.makeConnection = PatchedProtocolWrapper.makeConnection
ProtocolWrapper.dataReceived = PatchedProtocolWrapper.dataReceived
ProtocolWrapper.connectionLost = PatchedProtocolWrapper.connectionLost
# applying the patch for ThrottlingFactory
ThrottlingFactory.log = Logger()
ThrottlingFactory.buildProtocol = PatchedThrottlingFactory.buildProtocol
# applying patch for LimitConnectionsByPeer
LimitConnectionsByPeer.buildProtocol = PatchedLimitConnectionsByPeer.buildProtocol
LimitConnectionsByPeer.unregisterProtocol = PatchedLimitConnectionsByPeer.unregisterProtocol


class HTTPRequest(AbstractApplicationInterfaceProtocol, Request):
    log = Logger()

    def process(self):
        """
        Dispatches the request processing to background thread.

        :return: <void>
        """
        reactor.callInThread(self.parseRequest)

    def parseRequest(self):
        """
        Parses request by validating URL, decoding parameters, authenticating contents, and forwards the execution
        to the application's dispatcher.

        :return: <void>
        """
        super(HTTPRequest, self).setup()

        if self.channel is None:
            self.failRequestWithErrors(["CannotPerformRequest"])
            return

        requestUri = self.path.decode()
        segmentsUri = requestUri.split("/")

        # validating URI
        if len(segmentsUri) != 3:
            self.failRequestWithErrors(["InvalidRequestUri", requestUri])
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
        if b"parameters" in self.args:
            try:
                requestParameters = json.loads(
                    self.args[b"parameters"][0].decode()
                )
            except json.JSONDecodeError:
                self.failRequestWithErrors(["InvalidParametersFormat"])
                return

        # performing message authentication using HMAC validation
        if len(self.channel.application.config["interface"]["http"]["authentication"]["key"]) > 0:
            # validating time
            if b"time" not in self.args:
                self.failRequestAuthenticationWithErrors(["SignatureTimeMissing"])
                return

            if len(self.args[b"time"][0].decode()) <= 0:
                self.failRequestAuthenticationWithErrors(["SignatureTimeMissing"])
                return

            try:
                requestSignatureTime = int(self.args[b"time"][0].decode())
            except ValueError:
                self.failRequestAuthenticationWithErrors(["SignatureTimeNotInteger"])
                return

            if abs(timegm(datetime.utcnow().utctimetuple()) - requestSignatureTime) > int(
                    self.channel.application.config["interface"]["http"]["authentication"]["maximumTimeOffset"]):
                self.failRequestAuthenticationWithErrors(["SignatureTimeExpired"])
                return

            # validating signature
            if b"signature" not in self.args:
                self.failRequestAuthenticationWithErrors(["SignatureMissing"])
                return

            if len(self.args[b"signature"][0].decode()) <= 0:
                self.failRequestAuthenticationWithErrors(["SignatureMissing"])
                return

            requestParametersString = ""
            if b"parameters" in self.args:
                requestParametersString = self.args[b"parameters"][0].decode()

            payloadSignature = "{}|{}".format(requestParametersString, requestSignatureTime)
            signature = hmac.new(
                self.channel.application.config["interface"]["http"]["authentication"]["key"].encode(),
                payloadSignature.encode(),
                digestmod=hashlib.sha512
            )

            if not hmac.compare_digest(signature.hexdigest(), self.args[b"signature"][0].decode()):
                self.failRequestAuthenticationWithErrors(["SignatureInvalid"])
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

    def failRequestAuthenticationWithErrors(self, errors):
        self.requestResponse["code"] = 401
        self.requestResponse["content"] = None
        self.requestResponse["errors"] += errors

        self.sendFinalRequestResponse()

    #
    # AbstractApplicationInterfaceProtocol
    #
    def getIPAddress(self):
        return self.getClientIP()

    def requestPassedDispatcherValidation(self):
        pass

    def failRequestWithErrors(self, errors):
        self.requestResponse["code"] = 400
        self.requestResponse["content"] = None
        self.requestResponse["errors"] += errors

        self.sendFinalRequestResponse()

    def sendPartialRequestResponse(self):
        # HTTP does not support partial response
        pass

    def sendFinalRequestResponse(self):
        def clearResponseCallback():
            # clearing response
            self.requestResponse["code"] = 0
            self.requestResponse["content"] = None
            self.requestResponse["errors"] = []

        def sendResponseCallback():
            try:
                responseCode = HTTPResponseCode(self.requestResponse["code"])

                # sending response
                self.setResponseCode(responseCode.code, responseCode.getMessage().encode())
                self.setHeader("Content-Type", "application/json")
                self.write(json.dumps(
                    {
                        "Content": self.requestResponse["content"],
                        "Errors": self.requestResponse["errors"]
                    },
                    sort_keys=True
                ).encode())
            except Exception as e:
                try:
                    responseCode = HTTPResponseCode(500)

                    self.setResponseCode(responseCode.code, responseCode.getMessage().encode())
                    self.setHeader("Content-Type", "application/json")
                    self.write(json.dumps(
                        {
                            "Content": None,
                            "Errors": []
                        },
                        sort_keys=True
                    ).encode())

                    self.log.error("[HTTP]: Error sendFinalRequestResponse(): {error}", error=str(e))
                except Exception as e:
                    self.log.error(
                        "[HTTP]: Error sendFinalRequestResponse(): Cannot send 500: {error}",
                        error=str(e)
                    )

            # closing connection
            keepAlive = False
            if hasattr(self, "channel") and self.channel is not None \
                    and self.channel.application.config["interface"]["http"]["connection"]["keepAlive"] != 0:
                keepAlive = True

            self.finish()
            if not keepAlive:
                self.transport.loseConnection()

            clearResponseCallback()

        # checking if any of the enabled policies closed the channel
        if hasattr(self, "channel") and self.channel is not None:
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

        :return: <void>
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

        :return: <void>
        """
        self._abortingCall = None

        try:
            self.transport.abortConnection()
        except:
            # connection is already ended
            pass


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
        """
        Starts the HTTP/S interface and attaches it to the application.

        :return: <void>
        """
        # validating configuration
        if self.application.config["interface"]["http"]["connection"]["maximum"] < \
                self.application.config["interface"]["http"]["connection"]["maximumByPeer"]:
            raise ValueError(
                "[HTTP]: You cannot set the total number of connections allowed lower than the total connections " \
                "per peer."
            )

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
        httpConnectionLimitFactory.maxConnectionsPerPeer = \
            self.application.config["interface"]["http"]["connection"]["maximumByPeer"]

        # enabling throttle policy
        httpThrottleFactory = ThrottlingFactory(
            httpConnectionLimitFactory,
            self.application.config["interface"]["http"]["connection"]["maximum"]
        )

        # starting default (unsecure) http interface
        if self.application.config["interface"]["http"]["default"]["enabled"]:
            if len(self.application.config["interface"]["http"]["ip"]) == 0:
                self._reactor = reactor.listenTCP(
                    self.application.config["interface"]["http"]["default"]["port"],
                    httpThrottleFactory,
                    self.application.config["interface"]["http"]["connection"]["queueSize"]
                )
            else:
                for interfaceIP in self.application.config["interface"]["http"]["ip"]:
                    self._reactor = reactor.listenTCP(
                        self.application.config["interface"]["http"]["default"]["port"],
                        httpThrottleFactory,
                        self.application.config["interface"]["http"]["connection"]["queueSize"],
                        interfaceIP
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
                privateKeyPassphrase = \
                    self.application.config["interface"]["http"]["tls"]["privateKeyPassphrase"].encode()
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

            if len(self.application.config["interface"]["http"]["ip"]) == 0:
                self._reactor = reactor.listenSSL(
                    self.application.config["interface"]["http"]["tls"]["port"],
                    httpThrottleFactory,
                    certificateOptions,
                    self.application.config["interface"]["http"]["connection"]["queueSize"]
                )
            else:
                for interfaceIP in self.application.config["interface"]["http"]["ip"]:
                    self._reactor = reactor.listenSSL(
                        self.application.config["interface"]["http"]["tls"]["port"],
                        httpThrottleFactory,
                        certificateOptions,
                        self.application.config["interface"]["http"]["connection"]["queueSize"],
                        interfaceIP
                    )


    def stopService(self):
        """
        Stops the HTTP/S interface and deattaches it from the application.

        :return: <void>
        """
        self._reactor.stopListening()

class HTTPResponseCode:
    messages = {
        # 1xx Informational response
        "100": "Continue",
        "101": "Switching Protocols",
        "102": "Processing",
        "103": "Early Hints",

        # 2xx Success
        "200": "OK",
        "201": "Created",
        "202": "Accepted",
        "203": "Non-Authoritative Information",
        "204": "No Content",
        "205": "Reset Content",
        "206": "Partial Content",
        "207": "Multi-Status",
        "208": "Already Reported",
        "226": "IM Used",

        # 3xx Redirection
        "300": "Multiple Choices",
        "301": "Moved Permanently",
        "302": "Found",
        "303": "See Other",
        "304": "Not Modified",
        "305": "Use Proxy",
        "306": "Switch Proxy",
        "307": "Temporary Redirect",
        "308": "Permanent Redirect",

        # 4xx Client errors
        "400": "Bad Request",
        "401": "Unauthorized",
        "402": "Payment Required",
        "403": "Forbidden",
        "404": "Not Found",
        "405": "Method Not Allowed",
        "406": "Not Acceptable",
        "407": "Proxy Authentication Required",
        "408": "Request Timeout",
        "409": "Conflict",
        "410": "Gone",
        "411": "Length Required",
        "412": "Precondition Failed",
        "413": "Payload Too Large",
        "414": "URI Too Long",
        "415": "Unsupported Media Type",
        "416": "Range Not Satisfiable",
        "417": "Expectation Failed",
        "418": "I'm a teapot",
        "421": "Misdirected Request",
        "422": "Unprocessable Entity",
        "423": "Locked",
        "424": "Failed Dependency",
        "425": "Too Early",
        "426": "Upgrade Required",
        "428": "Precondition Required",
        "429": "Too Many Requests",
        "431": "Request Header Fields Too Large",
        "451": "Unavailable For Legal Reasons",

        # 5xx Server errors
        "500": "Internal Server Error",
        "501": "Not Implemented",
        "502": "Bad Gateway",
        "503": "Service Unavailable",
        "504": "Gateway Timeout",
        "505": "HTTP Version Not Supported",
        "506": "Variant Also Negotiates",
        "507": "Insufficient Storage",
        "508": "Loop Detected",
        "510": "Not Extended",
        "511": "Network Authentication Required"
    }

    def __init__(self, code):
        self.code = code

    def getMessage(self):
        if str(self.code) in self.messages:
            return self.messages[str(self.code)]

        return ""
