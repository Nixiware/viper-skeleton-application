from zope.interface import directlyProvides, providedBy

from twisted.logger import Logger
from twisted.protocols.policies import Protocol, ProtocolWrapper, WrappingFactory, ThrottlingFactory, LimitConnectionsByPeer


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
