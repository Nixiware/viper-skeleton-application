import os

from twisted.application import service

from nx.viper.application import ViperApplicationTwistedService

# instancing Twisted application
application = service.Application(os.path.basename(os.getcwd()))

# instancing Viper application service
viperApplicationService = ViperApplicationTwistedService()
viperApplicationService.setServiceParent(application)

# attaching Viper application interfaces
interfaces = viperApplicationService.viperApplication.getInterfaces()
for interfaceName, interface in interfaces.items():
    interface.setServiceParent(application)
