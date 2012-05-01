import sys

def lookup_attr(obj, key):
    try:
        return getattr(obj, key)
    except AttributeError:
        exc = sys.exc_info()[1]
        try:
            get = obj.__getitem__
        except AttributeError:
            raise exc
        try:
            return get(key)
        except KeyError:
            raise exc
