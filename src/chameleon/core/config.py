import os
import utils

# define which values are read as true
TRUEVALS = ('y', 'yes', 't', 'true', 'on', '1')

# in debug-mode, templates on disk are reloaded if they're modified
DEBUG_MODE_KEY = 'CHAMELEON_DEBUG'
DEBUG_MODE = os.environ.get(DEBUG_MODE_KEY, 'false')
DEBUG_MODE = DEBUG_MODE.lower() in TRUEVALS

# disable disk-cache to prevent the compiler from caching on disk
DISK_CACHE_KEY = 'CHAMELEON_CACHE'
DISK_CACHE = os.environ.get(DISK_CACHE_KEY, 'false')
DISK_CACHE = DISK_CACHE.lower() in TRUEVALS

# if eager parsing is enabled, templates are parsed upon
# instantiation, rather than when first called upon; this mode is
# useful for verifying validity of templates across a project
EAGER_PARSING_KEY = 'CHAMELEON_EAGER'
EAGER_PARSING = os.environ.get(EAGER_PARSING_KEY, 'false')
EAGER_PARSING = EAGER_PARSING.lower() in TRUEVALS

# in strict mode, filled macro slots must exist in the macro that's
# being used.
STRICT_MODE_KEY = 'CHAMELEON_STRICT'
STRICT_MODE = os.environ.get(STRICT_MODE_KEY, 'false')
STRICT_MODE = STRICT_MODE.lower() in TRUEVALS

# when validation is enabled, dynamically inserted content is
# validated against the XHTML standard
VALIDATION_KEY = 'CHAMELEON_VALIDATE'
VALIDATION = os.environ.get(VALIDATION_KEY, 'false')
VALIDATION = VALIDATION.lower() in TRUEVALS

# these definitions are standard---change at your own risk!
XML_NS = "http://www.w3.org/XML/1998/namespace"
XHTML_NS = "http://www.w3.org/1999/xhtml"
TAL_NS = "http://xml.zope.org/namespaces/tal"
META_NS = "http://xml.zope.org/namespaces/meta"
METAL_NS = "http://xml.zope.org/namespaces/metal"
XI_NS = "http://www.w3.org/2001/XInclude"
I18N_NS = "http://xml.zope.org/namespaces/i18n"
PY_NS = "http://genshi.edgewall.org/"

DEFAULT_ENCODING = "utf-8"

# default prefix namespace mapping
DEFAULT_NS_MAP = {
    None: XHTML_NS,
    'xml': XML_NS,
    'meta': META_NS,
    'py': PY_NS,
    'tal': TAL_NS,
    'metal': METAL_NS,
    'i18n': I18N_NS,
    'xi': XI_NS}

TRANSIENT_SYMBOL = object()

# the symbols table below is used internally be the compiler
class SYMBOLS(object):
    # internal use only
    init = '_init'
    callback = '_callback'
    slots = '_slots'
    metal = '_metal'
    include = '_include'
    macro = '_macro'
    out = '_out'
    tmp = '_tmp'
    write = '_write'
    mapping = '_mapping'
    result = '_result'
    marker = '_marker'
    domain = '_domain'
    i18n_context = '_i18n_context'
    attributes = '_attributes'
    negotiate = '_negotiate'
    translate = '_translate'
    validate = '_validate'
    msgid = '_msgid'
    re_amp = '_re_amp'
    raise_exc = '_raise_exc'

    # transient
    _slots = TRANSIENT_SYMBOL
    _translate = TRANSIENT_SYMBOL
    target_language = TRANSIENT_SYMBOL

    # markers
    default_marker = utils.default()
    default_marker_symbol = '_default'

    # advertised symbols
    repeat = 'repeat'
    language = 'target_language'
    xincludes = 'xincludes'
    default = 'default'
    scope = 'econtext'
    remote_scope = 'rcontext'

    def __new__(cls, **kwargs):
        class SYMBOLS(cls):
            pass

        for name, value in kwargs.items():
            setattr(SYMBOLS, name, value)

        return SYMBOLS

    @classmethod
    def as_dict(cls):
        return dict((name, getattr(cls, name)) for name in dir(cls))
