import sys


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
