try:
    from zope.interface import implements
except ImportError:
    def implements(*interfaces):
        pass

try:
    from zope.component import queryUtility
    from zope.component import queryAdapter
    from zope.component import adapts
except ImportError:
    def queryUtility(*args, **kw):
        return
    def queryAdapter(*args, **kw):
        return
    def adapts(*interfaces):
        pass

import sys
import interfaces
import htmlentitydefs
import re
import xml.parsers.expat

types = sys.modules['types']

from UserDict import UserDict

# check if we're able to coerce unicode to str
try:
    str(u'La Pe\xf1a')
    unicode_required_flag = False
except UnicodeEncodeError:
    unicode_required_flag = True

def coerces_gracefully(encoding):
    if encoding != sys.getdefaultencoding() and unicode_required_flag:
        return False
    return True

entities = "".join((
    '<!ENTITY %s "&amp;%s;">' % (name, name) for (name, text) in \
    htmlentitydefs.name2codepoint.items()))

re_annotation = re.compile(r'^\s*u?[\'"](.*)[\'"]$')
re_entity = re.compile(r'&([A-Za-z]+|#[0-9]+);')
re_numeric_entity = re.compile(r'&#([0-9]+);')
re_amp = re.compile(r'&(?!([A-Za-z]+|#[0-9]+);)');
re_meta = re.compile(
    r'\s*<meta\s+http-equiv=["\']?Content-Type["\']?'
    r'\s+content=["\']?([^;]+);\s*charset=([^"\']+)["\']?\s*/?\s*>\s*',
    re.IGNORECASE)

XML_PREFIXES = [
    "<?xml",                      # ascii, utf-8
    "\xef\xbb\xbf<?xml",          # utf-8 w/ byte order mark
    "\0<\0?\0x\0m\0l",            # utf-16 big endian
    "<\0?\0x\0m\0l\0",            # utf-16 little endian
    "\xfe\xff\0<\0?\0x\0m\0l",    # utf-16 big endian w/ byte order mark
    "\xff\xfe<\0?\0x\0m\0l\0",    # utf-16 little endian w/ byte order mark
    ]

XML_PREFIX_MAX_LENGTH = max(map(len, XML_PREFIXES))

s_counter = 0
marker = object()

class callablestr(str):
    __slots__ = ()

    def __call__(self):
        return self

class callableint(int):
    __slots__ = ()

    def __call__(self):
        return self

class descriptorstr(object):
    __slots__ = "function", "__name__"

    def __init__(self, function):
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context, cls):
        return callablestr(self.function(context))

class descriptorint(object):
    __slots__ = "function", "__name__"

    def __init__(self, function):
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context, cls):
        return callableint(self.function(context))

def sniff_type(text):
    """Return 'text/xml' if text appears to be XML, otherwise return None."""
    for prefix in XML_PREFIXES:
        if text.startswith(prefix):
            return "text/xml"
    return None

def handler(key=None):
    def decorate(f):
        def g(node):
            if key is None:
                return f(node, None)
            return f(node, node.get(key))
        g.__ns__ = key
        return g
    return decorate

def import_elementtree():
    """The ElementTree is used to validate output in debug-mode. We
    attempt to load the library from several locations."""
    
    try:
        import xml.etree.ElementTree as ET
    except:
        try:
            import elementtree.ElementTree as ET
        except ImportError:
            import cElementTree as ET
        
    return ET

def validate(string):
    """Wraps string as a proper HTML document and validates it by
    attempting to parse it using the active ElementTree parser."""
    
    validation_string = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" [ %s ]><div>%s</div>' % (
        entities, string)
    
    try:
        import_elementtree().fromstring(validation_string)
    except xml.parsers.expat.ExpatError:
        raise ValidationError(string)

def elements_with_attribute(element, ns, name, value=None):
    """Returns elements on the 'descendant-or-self' axis that has
    ``attribute`` (in qualified namespace notation).

    If ``value`` is specified, only elemmnts with this attribute value
    are returned.
    """

    return tuple(_elements_with_attribute(element, ns, name, value))

def _elements_with_attribute(element, ns, name, value):
    element_ns = get_namespace(element)
    if element_ns == ns:
        _value = element.attrib.get(name, marker)
    else:
        _value = marker

    if _value is marker:
        _value = element.attrib.get('{%s}%s' % (ns, name), marker)

    if value is not None:
        if value == _value:
            yield element
    elif _value is not marker:
        yield element

    for child in element:
        for match in _elements_with_attribute(child, ns, name, value):
            yield match

class attribute(property):
    def __init__(self, tokens, factory=None, default=None, encoding=None, recursive=False):
        self.tokens = tokens
        self.factory = factory
        self.default = default
        self.encoding = encoding
        self.recursive = recursive
        property.__init__(self, self.__call__)

    def __call__(attribute, element):
        value = attribute.get(element)
        if value is not None:
            encoding = attribute.encoding
            if encoding is None:
                try:
                    encoding = element.stream.encoding
                except AttributeError:
                    pass
            if encoding:
                value = value.encode(encoding, 'xmlcharrefreplace')
            if attribute.factory is None:
                return value
            f = attribute.factory(element.translator)
            return f(value)

        if attribute.recursive:
            parent = element.getparent()
            if parent is not None:
                return attribute(parent)

        if attribute.default is not None:
            return attribute.default

    def get(attribute, element):
        tokens = attribute.tokens
        for token in isinstance(tokens, tuple) and tokens or (tokens,):
            value = element.attrib.get(token)
            if value is not None:
                return value

def escape(string, quote=None, encoding=None):
    if not isinstance(string, unicode) and encoding:
        string = string.decode(encoding)
    else:
        encoding = None

    string = re_amp.sub('&amp;', string).\
             replace('<', '&lt;').\
             replace('>', '&gt;')

    if quote is not None:
        string = string.replace(quote, '\\'+quote)

    if encoding:
        string = string.encode(encoding)

    return string

def htmlescape(text):
    while text:
        m = re_amp.search(text)
        if m is None:
            break
        text = text[:m.start()] + re_amp.sub("&amp;", text[m.start():], 1)

    return text.replace('<', '&lt;').replace('>', '&gt;')

re_normalize = re.compile(r'(^[0-9]|\b[^A-Za-z])')
def normalize_slot_name(name):
    return re_normalize.sub('_', name)

def serialize(element, encoding=None, omit=False):
    return "".join(serialize_element(element, encoding, omit=omit))

def serialize_element(element, encoding, omit):
    try:
        name = element.tag.split('}')[-1]
    except AttributeError:
        yield htmlescape(element.text); return

    if omit is False:
        # tag opening
        yield "<%s" % name

        # attributes
        for key, value in element.attrib.items():
            yield ' %s="%s"' % (key, escape('"', encoding=encoding))

        # elements with no text which have no children are self-closing.
        if element.text is None and len(element) == 0:
            yield ' />'; return

        yield '>'
            
    if element.text is not None:
        yield htmlescape(element.text)

    for child in element:
        for string in serialize_element(child, encoding, False):
            yield string

    if omit is False:
        yield '</%s>' % name

def class_hierarchy(cls):
    """Return an unordered sequence of all classes related to cls.

    Traverses diamond hierarchies.

    Fibs slightly: subclasses of builtin types are not returned.  Thus
    class_hierarchy(class A(object)) returns (A, object), not A plus every
    class systemwide that derives from object.

    Old-style classes are discarded and hierarchies rooted on them
    will not be descended.

    """
    if isinstance(cls, types.ClassType):
        return list()
    hier = set([cls])
    process = list(cls.__mro__)
    while process:
        c = process.pop()
        if isinstance(c, types.ClassType):
            continue
        for b in (_ for _ in c.__bases__
                  if _ not in hier and not isinstance(_, types.ClassType)):
            process.append(b)
            hier.add(b)
        if c.__module__ == '__builtin__' or not hasattr(c, '__subclasses__'):
            continue
        for s in [_ for _ in c.__subclasses__() if _ not in hier]:
            process.append(s)
            hier.add(s)
    return list(hier)

class default(object):
    __slots__ = 'value',

    def __init__(self):
        self.value = None

    def __setitem__(self, key, value):
        self.value = value

    def __html__(self):
        return self.value

class econtext(dict):
    """Dynamic scope dictionary which is compatible with the
    `econtext` of ZPT."""

    set_local = setLocal = dict.__setitem__
    set_global = setGlobal = dict.__setitem__

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            raise NameError(key)

    @property
    def vars(self):
        return self

    def copy(self):
        inst = econtext(self)
        inst.set_global = self.set_global
        return inst

class scope(list):
    def __init__(self, *args):
        global s_counter
        self.hash = s_counter
        s_counter += 1

    def __hash__(self):
        return self.hash

class emptydict(dict):
    def __setitem__(self, key, value):
        raise RuntimeError("Read-only dictionary does not support assignment.")

    def update(self, dictionary):
        raise RuntimeError("Read-only dictionary does not support assignment.")

emptydict = emptydict()

class repeatitem(object):
    implements(interfaces.ITALESIterator)

    __slots__ = "length", "_iterator"

    def __init__(self, iterator, length):
        self.length = length
        self._iterator = iterator

    try:
        iter(()).__len__
    except AttributeError:
        @property
        def index(self):
            remaining = self._iterator.__length_hint__()
            return self.length - remaining - 1
    else:
        @property
        def index(self):
            remaining = self._iterator.__len__()
            return self.length - remaining - 1

    @property
    def start(self):
        return self.index == 0

    @property
    def end(self):
        return self.index == self.length - 1

    @descriptorint
    def number(self):
        return self.index + 1

    @descriptorstr
    def odd(self):
        """Returns a true value if the item index is odd.

        >>> it = repeatitem(iter(("apple", "pear")), 2)

        >>> it._iterator.next()
        'apple'
        >>> it.odd()
        ''

        >>> it._iterator.next()
        'pear'
        >>> it.odd()
        'odd'
        """

        return self.index % 2 == 1 and 'odd' or ''

    @descriptorstr
    def even(self):
        """Returns a true value if the item index is even.

        >>> it = repeatitem(iter(("apple", "pear")), 2)

        >>> it._iterator.next()
        'apple'
        >>> it.even()
        'even'

        >>> it._iterator.next()
        'pear'
        >>> it.even()
        ''
        """

        return self.index % 2 == 0 and 'even' or ''

    def next(self):
        raise NotImplementedError(
            "Method not implemented (can't update local variable).")

    def _letter(self, base=ord('a'), radix=26):
        """Get the iterator position as a lower-case letter

        >>> it = repeatitem(iter(("apple", "pear", "orange")), 3)
        >>> it._iterator.next()
        'apple'
        >>> it.letter()
        'a'
        >>> it._iterator.next()
        'pear'
        >>> it.letter()
        'b'
        >>> it._iterator.next()
        'orange'
        >>> it.letter()
        'c'
        """

        index = self.index
        if index < 0:
            raise TypeError("No iteration position")
        s = ""
        while 1:
            index, off = divmod(index, radix)
            s = chr(base + off) + s
            if not index:
                return s

    letter = descriptorstr(_letter)

    @descriptorstr
    def Letter(self):
        """Get the iterator position as an upper-case letter

        >>> it = repeatitem(iter(("apple", "pear", "orange")), 3)
        >>> it._iterator.next()
        'apple'
        >>> it.Letter()
        'A'
        >>> it._iterator.next()
        'pear'
        >>> it.Letter()
        'B'
        >>> it._iterator.next()
        'orange'
        >>> it.Letter()
        'C'
        """

        return self._letter(base=ord('A'))

    @descriptorstr
    def Roman(self, rnvalues=(
                    (1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),
                    (100,'C'),(90,'XC'),(50,'L'),(40,'XL'),
                    (10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')) ):
        """Get the iterator position as an upper-case roman numeral

        >>> it = repeatitem(iter(("apple", "pear", "orange")), 3)
        >>> it._iterator.next()
        'apple'
        >>> it.Roman()
        'I'
        >>> it._iterator.next()
        'pear'
        >>> it.Roman()
        'II'
        >>> it._iterator.next()
        'orange'
        >>> it.Roman()
        'III'
        """

        n = self.index + 1
        s = ""
        for v, r in rnvalues:
            rct, n = divmod(n, v)
            s = s + r * rct
        return s

    @descriptorstr
    def roman(self):
        """Get the iterator position as a lower-case roman numeral

        >>> it = repeatitem(iter(("apple", "pear", "orange")), 3)
        >>> it._iterator.next()
        'apple'
        >>> it.roman()
        'i'
        >>> it._iterator.next()
        'pear'
        >>> it.roman()
        'ii'
        >>> it._iterator.next()
        'orange'
        >>> it.roman()
        'iii'
        """

        return self.Roman().lower()

class repeatdict(dict):
    __slots__ = ()

    def insert(self, key, iterable):
        """We coerce the iterable to a tuple and return an iterator
        after registering it in the repeat dictionary."""

        try:
            iterable = tuple(iterable)
        except TypeError:
            if iterable is None:
                iterable = ()
            else:
                # The message below to the TypeError is the Python
                # 2.5-style exception message. Python 2.4.X also
                # raises a TypeError, but with a different message.
                # ("TypeError: iteration over non-sequence").  The
                # Python 2.5 error message is more helpful.  We
                # construct the 2.5-style message explicitly here so
                # that both Python 2.4.X and Python 2.5+ will raise
                # the same error.  This makes writing the tests eaiser
                # and makes the output easier to understand.
                raise TypeError("%r object is not iterable" %
                                type(iterable).__name__)

        length = len(iterable)
        iterator = iter(iterable)

        # insert item into repeat-dictionary
        self[key] = iterator, length, None

        return iterator, length

    def __getitem__(self, key):
        iterator, length, repeat = dict.__getitem__(self, key)
        if repeat is None:
            repeat = repeatitem(iterator, length)
            self[key] = iterator, length, repeat
        return repeat

    __getattr__ = __getitem__

    def get(self, key, default):
        if key not in self:
            return default
        return self[key]

class odict(UserDict):
    def __init__(self, dict = None):
        self._keys = []
        UserDict.__init__(self, dict)

    def __delitem__(self, key):
        UserDict.__delitem__(self, key)
        self._keys.remove(key)

    def __setitem__(self, key, item):
        """Case insensitive set item."""

        keys = tuple(key.lower() for key in self._keys)
        _key = key.lower()
        if _key in keys:
            for k in self._keys:
                if k == _key:
                    key = k
                    break
                elif k.lower() == _key:
                    self._keys.remove(k)
                    key = k
                    break

        UserDict.__setitem__(self, key, item)
        
        if key not in self._keys:
            self._keys.append(key)

    def __iter__(self):
        return iter(self._keys)
    
    def clear(self):
        UserDict.clear(self)
        self._keys = []

    def copy(self):
        dict = UserDict.copy(self)
        dict._keys = self._keys[:]
        return dict

    def items(self):
        return zip(self._keys, self.values())

    def keys(self):
        return self._keys

    def popitem(self):
        try:
            key = self._keys[-1]
        except IndexError:
            raise KeyError('dictionary is empty')

        val = self[key]
        del self[key]

        return (key, val)

    def setdefault(self, key, failobj = None):
        UserDict.setdefault(self, key, failobj)
        if key not in self._keys: self._keys.append(key)

    def update(self, dict):
        UserDict.update(self, dict)
        for key in dict.keys():
            if key not in self._keys: self._keys.append(key)

    def values(self):
        return map(self.get, self._keys)

def dotted_name(cls):
    return "%s.%s" % (cls.__module__, cls.__name__)

def get_attributes_from_namespace(element, namespace):
    if namespace is None:
        attrs = dict([
            (name, value) for (name, value) in element.attrib.items() \
            if '{' not in name])
    else:
        attrs = dict([
            (name, value) for (name, value) in element.attrib.items() \
            if name.startswith('{%s}' % namespace)])

    return attrs

def format_attribute(element, key):
    if '}' not in key:
        return key
    ns, name = key[1:].split('}')
    for prefix, namespace in element.nsmap.items():
        if ns == namespace:
            return '%s:%s' % (prefix, name)
    for prefix, namespace in config.DEFAULT_NS_MAP.items():
        if ns == namespace:
            return '%s:%s' % (prefix, name)
    raise ValueError("Can't format attribute: %s." % key)

def get_namespace(element):
    if not isinstance(element.tag, basestring):
        return
    if '}' in element.tag:
        return element.tag.split('}')[0][1:]
    return element.nsmap.get(None)

def format_kwargs(kwargs):
    items = []
    for name, value in kwargs.items():
        if isinstance(value, (int, float, basestring)):
            items.append((name, value))
        elif isinstance(value, dict):
            items.append((name, '{...} (%d)' % len(value)))
        else:
            items.append((name,
                "<%s %s at %s>" % (
                    type(value).__name__,
                    getattr(value, '__name__', "-"),
                    hex(id(value)))))

    return ["%s: %s" % item for item in items]

def raise_exc(exc):
    raise exc

def raise_template_exception(description, kwargs, exc_info):
    """Re-raise exception raised while calling ``template``, given by
    the ``exc_info`` tuple (see ``sys.exc_info``)."""

    kwargs = kwargs.copy()

    # merge dynamic scope
    kwargs.update(kwargs.pop('econtext', {}))

    # omit keyword arguments that begin with an underscore; these are
    # used internally be the template engine and should not be exposed
    map(kwargs.__delitem__, [k for k in kwargs if k.startswith('_')])

    # format keyword arguments; consecutive arguments are indented for
    # readability
    try:
        formatted_arguments = format_kwargs(kwargs)
    except:
        # the ``pprint.pformat`` method calls the representation
        # method of the arguments; this may fail and since we're
        # already in an exception handler, there's no point in
        # pursuing this further
        formatted_arguments = ()

    for index, string in enumerate(formatted_arguments[1:]):
        formatted_arguments[index+1] = " "*15 + string

    # extract line number from traceback object
    cls, exc, tb = exc_info
    try:
        lineno = tb.tb_next.tb_frame.f_lineno - 1
        filename = tb.tb_next.tb_frame.f_code.co_filename
        source = open(filename).read()
    except AttributeError:
        source = None

    # locate source code annotation (these are available from
    # the template source as comments)
    if source:
        source = source.split('\n')
        for i in reversed(range(lineno)):
            try:
                line = source[i]
            except IndexError:
                raise cls, exc, tb
            m = re_annotation.match(line)
            if m is not None:
                annotation = m.group(1)
                break
        else:
            annotation = ""

        error_msg = "Caught exception rendering template."
    else:
        annotation = ""
        error_msg = "Caught exception processing template: %s.\n" % description

    __dict__ = exc.__dict__
    __name__ = cls.__name__
    
    error_string = str(exc)

    if issubclass(cls, Exception):
        class RuntimeError(cls):
            def __init__(self, *args, **kwargs):
                pass
            
            def __str__(self):
                return "%s\n%s\n%s: %s" % (
                    error_msg, str(self.__debug_info__),
                    __name__, error_string)

        if isinstance(cls, types.TypeType):
            exc = RuntimeError.__new__(RuntimeError)
            exc.__dict__.update(__dict__)
        else:
            cls = RuntimeError

        # add/extend debug info
        try:
            debug_info = RuntimeError.__debug_info__
        except AttributeError:
            debug_info = RuntimeError.__debug_info__ = DebugInfo()
        debug_info.append(annotation, description, formatted_arguments)

    raise cls, exc, tb

class DebugInfo(object):
    def __init__(self):
        self.info = []
        
    def append(self, *args):
        self.info.append(args)

    def __str__(self):
        error_format = ' - Expression: "%s"\n' \
                       ' - Instance:   %s\n' \
                       ' - Arguments:  %s\n'

        annotation, description, formatted_arguments = self.info[-1]
        return error_format % (
            annotation, description, "\n".join(formatted_arguments))

class ValidationError(ValueError):
    def __str__(self):
        value, = self.args
        return "Insertion of %s is not allowed." % \
               repr(value)

# importing these here to avoid circular reference

import config

def xhtml_attr(name):
    return "{%s}%s" % (config.XHTML_NS, name)

def tal_attr(name):
    return "{%s}%s" % (config.TAL_NS, name)

def meta_attr(name):
    return "{%s}%s" % (config.META_NS, name)

def metal_attr(name):
    return "{%s}%s" % (config.METAL_NS, name)

def i18n_attr(name):
    return "{%s}%s" % (config.I18N_NS, name)

def py_attr(name):
    return "{%s}%s" % (config.PY_NS, name)
