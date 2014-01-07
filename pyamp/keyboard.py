import inspect


def bindable(func):
    '''Decorator used to label a function as bindable to a key (i.e. that a
    user can call it outright).
    '''
    spec = inspect.getargspec(func)
    # At the time we're decorating methods, they're not actually methods yet,
    # just callables with a first argument conventionally called self/cls :-(
    args = [arg for arg in spec.args if arg not in ('self', 'cls')]
    defaults = spec.defaults or ()
    if not len(args) == len(defaults):
        raise ValueError(
            "Can't decorate callable with non-defaulted arguments with "
            "@bindable ({})".format(spec))
    func.bindable = True
    return func


def is_bindable(func):
    '''Determines if the given function has been decorated as bindable.
    '''
    return getattr(func, 'bindable', False)
