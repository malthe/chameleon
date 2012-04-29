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

def exec_(code, globs=None, locs=None):
    """Execute code in a namespace."""
    if globs is None:
        frame = sys._getframe(1)
        globs = frame.f_globals
        if locs is None:
            locs = frame.f_locals
        del frame
    elif locs is None:
        locs = globs
    exec("""exec code in globs, locs""")


exec_("""def raise_with_traceback(exc, tb):
    raise type(exc), exc, tb
""")


def next(iter):
    return iter.next()
