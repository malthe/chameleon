def lookup_attr(obj, key):
    try:
        return getattr(obj, key)
    except AttributeError, exc:
        try:
            get = obj.__getitem__
        except AttributeError:
            raise exc
        try:
            return get(key)
        except KeyError:
            raise exc


def raise_with_traceback(exc, tb):
    raise type(exc), exc, tb


def next(iter):
    return iter.next()
