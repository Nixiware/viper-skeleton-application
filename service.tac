import sys, os
#sys.path.append(".")

from twisted.application import service

from nx.viper.application import ViperApplicationTwistedService

# instancing Twisted application
application = service.Application(os.path.basename(os.getcwd()))

# instancing Viper application service
viperApplicationService = ViperApplicationTwistedService()
viperApplicationService.setServiceParent(application)

# attaching Viper application interfaces
for interfaceName, interface in viperApplicationService.viperApplication.getInterfaces().items():
    interface.setServiceParent(application)