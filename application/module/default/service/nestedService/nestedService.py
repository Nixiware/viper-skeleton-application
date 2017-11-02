from application.module.default.service.nestedService.requiredComponent import RequiredComponent

class Service:
    def __init__(self, application):
        self.application = application
        self.requiredComponent = RequiredComponent()

    def performAction(self, string):
        return "{}.{}".format(string, string)
