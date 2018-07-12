from application.module.default.service.nestedService.requiredComponent import RequiredComponent

class Service:
    def __init__(self, application):
        self.application = application

        # example of loading class specifically for this service
        self.requiredComponent = RequiredComponent()

    def performAction(self, string):
        # format value is loaded from the config file located in module's config file
        return self.application.config["defaultFormat"].format(string, string)
