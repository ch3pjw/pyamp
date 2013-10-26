class ModuleProxy(object):
    def __init__(self, module=None):
        self.module = module

    def __getattr__(self, name):
        return getattr(self.module, name)


def clamp(value, min_=None, max_=None):
    if min_ is None:
        min_ = min(value, max_)
    if max_ is None:
        max_ = max(value, min_)
    return sorted((value, min_, max_))[1]
