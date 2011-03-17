import tempfile
import os

class _TemporaryFileWrapper:
    """Temporary file wrapper

    This class provides a wrapper around files opened for
    temporary use.  In particular, it seeks to automatically
    remove the file when it is no longer needed.
    """

    def __init__(self, name):
        self.close_called = False
        self.name = name

    def close(self):
        if not self.close_called:
            self.close_called = True
            os.unlink(self.name)

    def __del__(self):
        self.close()

    def __enter__(self):
        return self
    
    def __exit__(self, exc, value, tb):
        self.close()

def NamedTemporaryFile(suffix="", prefix=tempfile.template, dir=None):
    """Create and return a temporary file. The key difference with standard tempfile.NamedTemporaryFile
    is the object with filename only is returned, but the file itself should be opened by 
    NamedTemporaryFile caller.
    Arguments:
    'prefix', 'suffix', 'dir' -- as for mkstemp.
    The file is created as mkstemp() would do it.

    Returns an object with attribute 'name' - the name of the created temporary file.
    The file will be automatically deleted when it is closed.
    """

    if dir is None:
        dir = tempfile.gettempdir()

    (fd, name) = tempfile._mkstemp_inner(dir, prefix, suffix, tempfile._text_openflags)
    os.close(fd)
    return _TemporaryFileWrapper(name)
