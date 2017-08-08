from nx.viper.module import Module as ViperModule


class Module(ViperModule):
    def __init__(self, application):
        super(Module, self).__init__("default", __file__, application)
