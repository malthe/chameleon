import re

from chameleon.core.utils import implements
from chameleon.core.utils import queryUtility
from chameleon.core.utils import queryAdapter
from chameleon.core.utils import adapts
from chameleon.core import types
from chameleon.core import parsing
from chameleon.ast.astutil import parse

import interfaces

translators = {
    'python': lambda translator: python_translator,
    'string': lambda translator: StringTranslator(translator),
    'import': lambda translator: ImportTranslator()}

def lookup_translator(current, name):
    """Look up translator. Priority is given to translators registered
    as components. If a component lookup fails, use the module-global
    ``translators`` dictionary.

    The recommended way to add new translators is to use the component
    architecture.
    """

    translator = queryUtility(
        interfaces.IExpressionTranslator, name=name) or \
        queryAdapter(
        current, interfaces.IExpressionTranslator, name=name)

    if translator is not None:
        return translator

    function = translators.get(name)
    if function is not None:
        return function(current)

class ExpressionTranslator(object):
    """Base class for TALES expression translation."""

    implements(interfaces.IExpressionTranslator)

    re_pragma = re.compile(r'^\s*(?P<pragma>[a-z]+):')
    re_method = re.compile(r'^(?P<name>[A-Za-z0-9_]+)'
                           '(\((?P<args>[A-Za-z0-9_]+\s*(,\s*[A-Za-z0-9_]+)*)\))?')

    recursive = False

    def __init__(self):
        self.translator = self

    def pragma(self, name):
        return lookup_translator(self, name)

    def declaration(self, string):
        """Variable declaration.

        >>> declaration = ExpressionTranslator().declaration

        Single variable:

        >>> declaration("variable")
        declaration('variable')

        Multiple variables:

        >>> declaration("variable1, variable2")
        declaration('variable1', 'variable2')

        >>> declaration("variable1,variable2")
        declaration('variable1', 'variable2')

        Repeat not allowed:

        >>> declaration('repeat')
        Traceback (most recent call last):
         ...
        ValueError: Invalid variable name 'repeat' (reserved).

        >>> declaration('_disallowed')
        Traceback (most recent call last):
         ...
        ValueError: Invalid variable name '_disallowed' (starts with an underscore).
        """

        variables = []
        for var in string.split(','):
            var = var.strip()

            if var in ('repeat',):
                raise ValueError, "Invalid variable name '%s' (reserved)." % var

            if var.startswith('_') and not var.startswith('_tmp'):
                raise ValueError(
                    "Invalid variable name '%s' (starts with an underscore)." % var)

            variables.append(var)

        return types.declaration(variables)

    def mapping(self, string):
        """Semicolon-separated mapping.
        
        >>> mapping = ExpressionTranslator().mapping

        >>> mapping("abc def")
        mapping(('abc', 'def'),)

        >>> mapping("abc def;")
        mapping(('abc', 'def'),)

        >>> mapping("abc")
        mapping(('abc', None),)

        >>> mapping("abc;")
        mapping(('abc', None),)

        >>> mapping("abc; def ghi")
        mapping(('abc', None), ('def', 'ghi'))
        """

        defs = string.split(';')
        mappings = []
        for d in defs:
            d = d.strip()
            if d == '':
                continue
            parts = d.split()
            if len(parts) == 1:
                mappings.append((d, None))
            elif len(parts) == 2:
                mappings.append((parts[0], parts[1]))
            else:
                raise ValueError, "Invalid mapping (%s)." % string

        return types.mapping(mappings)

    def definitions(self, string):
        """Semi-colon separated variable definitions.
        
        >>> class MockExpressionTranslator(ExpressionTranslator):
        ...     def tales(self, string, escape=None):
        ...         if string == '' or ';' in string.replace("';'", "''"):
        ...             raise SyntaxError()
        ...         return types.value(string.strip())

        >>> definitions = MockExpressionTranslator().definitions
        
        Single define:
        
        >>> definitions("variable expression")
        definitions((declaration('variable'), value('expression')),)
        
        Multiple defines:
        
        >>> definitions("variable1 expression1; variable2 expression2")
        definitions((declaration('variable1'), value('expression1')),
                    (declaration('variable2'), value('expression2')))

        Defines are only split on semi-colon if a valid declaration is
        available.
        
        >>> definitions("variable1 ';'+expression1; variable2 expression2")
        definitions((declaration('variable1'), value("';'+expression1")),
                    (declaration('variable2'), value('expression2')))

        Tuple define:
        
        >>> definitions("(variable1, variable2) (expression1, expression2)")
        definitions((declaration('variable1', 'variable2'),
                    value('(expression1, expression2)')),)

        Global defines:

        >>> definitions("global variable expression")
        definitions((declaration('variable', global_scope=True), value('expression')),)

        >>> definitions("variable1 expression1; global variable2 expression2")
        definitions((declaration('variable1'), value('expression1')),
                    (declaration('variable2', global_scope=True), value('expression2')))

        Space, the 'in' operator and '=' may be used to separate
        variable from expression.

        >>> definitions("variable in expression")
        definitions((declaration('variable'), value('expression')),)        
        
        >>> definitions("variable1 = expression1; variable2 = expression2")
        definitions((declaration('variable1'), value('expression1')),
                    (declaration('variable2'), value('expression2')))

        >>> definitions("variable1=expression1; variable2=expression2")
        definitions((declaration('variable1'), value('expression1')),
                    (declaration('variable2'), value('expression2')))
        
        A define clause that ends in a semicolon:
        
        >>> definitions("variable expression;")
        definitions((declaration('variable'), value('expression')),)
        
        A define clause with a trivial expression (we do allow this):
        
        >>> definitions("variable")
        definitions((declaration('variable'), None),)
        
        A proper define clause following one with a trivial expression:
        
        >>> definitions("variable1 expression; variable2")
        definitions((declaration('variable1'), value('expression')),
                    (declaration('variable2'), None))
        """

        string = string.replace('\n', '').strip()

        defines = []
        i = 0
        while i < len(string):
            while string[i] == ' ':
                i += 1

            global_scope = False
            if string[i:].startswith('global'):
                global_scope = True
                i += 6

            # get variable definition
            if string[i] == '(':
                j = string.find(')', i+1)
                if j == -1:
                    raise ValueError, "Invalid variable tuple definition (%s)." % string
                var = self.declaration(string[i+1:j])
                j += 1
            else:
                j = string.find('=', i + 1)
                k = string.find(' ', i + 1)
                if k < j and k > -1 or j < 0:
                    j = k
                
                if j < 0:
                    var = self.declaration(string[i:])
                    j = len(string)
                else:
                    var = self.declaration(string[i:j])

            var.global_scope = global_scope

            # get expression
            i = j + len(string) - j - len(string[j:].lstrip())

            token = string[i:]
            if token.startswith('=='):
                raise ValueError("Invalid variable definition (%s)." % string)
            elif token.startswith('='):
                i += 1
            elif token.startswith('in '):
                i += 3

            try:
                expr = self.tales(string[i:], ';')
                j = -1
            except SyntaxError:
                expr = None
                j = len(string)

            while j > i:
                j = string.rfind(';', i, j)
                if j < 0:
                    # this is always a re-raise from right above
                    raise

                try:
                    expr = self.tales(string[i:j], ';')
                except SyntaxError:
                    if string.rfind(';', i, j) > 0:
                        continue
                    raise

                break

            defines.append((var, expr))

            if j < 0:
                break

            i = j + 1

        return types.definitions(defines)

    def definition(self, string):
        defs = self.definitions(string)
        if len(defs) != 1:
            raise ValueError, "Multiple definitions not allowed."

        return defs[0]

    def output(self, string):
        """String output; supports 'structure' keyword.
        
        >>> class MockExpressionTranslator(ExpressionTranslator):
        ...     def translate(self, string, escape=None):
        ...         if string: return types.value(string)

        >>> output = MockExpressionTranslator().output

        >>> output("context/title")
        escape(value('context/title'),)

        >>> output("context/pretty_title_or_id|context/title")
        escape(value('context/pretty_title_or_id'), value('context/title'))

        >>> output("structure context/title")
        value('context/title')        

        >>> output(" structure context/title")
        value('context/title')

        """

        string = string.lstrip(' ')
        if string.startswith('structure '):
            return self.tales(string[len('structure'):])
        
        expression = self.tales(string)

        if isinstance(expression, types.parts):
            return types.escape(expression)

        return types.escape((expression,))
            
    def tales(self, string, escape=None):
        """We need to implement the ``validate`` and
        ``translate``-methods. Let's define that an expression is
        valid if it contains an odd number of characters.
        
        >>> class MockExpressionTranslator(ExpressionTranslator):
        ...     def translate(self, string, escape=None):
        ...         if string: return types.value(string)

        >>> tales = MockExpressionTranslator().tales
                
        >>> tales('a')
        value('a')

        >>> tales('a|b')
        parts(value('a'), value('b'))
        """

        string = string.replace('\n', '').strip()

        if not string:
            return types.parts()

        parts = []

        # default translator is ``self``
        translator = self

        i = j = 0
        while i < len(string):
            match = self.re_pragma.match(string[i:])
            if match is not None:
                pragma = match.group('pragma')
                new_translator = self.pragma(pragma)
                if new_translator is not None:
                    translator = new_translator
                    i += match.end()
                    if translator.recursive:
                        value = translator.tales(string[i:])
                        if parts:
                            if isinstance(value, types.parts):
                                parts.extend(value)
                            else:
                                parts.append(value)

                            return types.parts(parts)
                        return value
                    continue

            j = string.find('|', j + 1)
            if j == -1:
                j = len(string)

            expr = string[i:j]

            try:
                value = translator.translate(expr, escape)
            except SyntaxError:
                if j < len(string):
                    continue
                raise

            value.label = expr
            parts.append(value)
            translator = self
            
            i = j + 1

        value = translator.translate("", escape)
        if value is not None:
            value.label = ""
            parts.append(value)

        if len(parts) == 1:
            return parts[0]

        return types.parts(parts)

    def split(self, string):
        return parsing.interpolate(string, self.translator.tales)

class PythonTranslator(ExpressionTranslator):
    """Implements Python expression translation."""

    def translate(self, string, escape=None):
        """We use the ``parser`` module to determine if
        an expression is a valid python expression.

        Make sure the syntax error exception contains the expression
        string.

        >>> translate = PythonTranslator().translate
        >>> try: translate('abc:def:ghi')
        ... except SyntaxError, e: 'abc:def:ghi' in repr(e)
        True
        """

        if isinstance(string, unicode):
            string = string.encode('utf-8')

        if string:
            expression = string.strip()
            parse(expression, 'eval')

            if isinstance(string, str):
                string = string.decode('utf-8')

            return types.value(string.strip())

python_translator = PythonTranslator()

class StringTranslator(ExpressionTranslator):
    """Implements string translation expression."""

    adapts(interfaces.IExpressionTranslator)
    
    re_interpolation = re.compile(r'(?P<prefix>[^\\]\$|^\$)({((?P<expression>.*)})?|'
                                  '(?P<variable>[A-Za-z][A-Za-z0-9_]*))')

    def __init__(self, translator):
        self.translator = translator

    def translate(self, string, escape=None):
        """
        >>> translate = StringTranslator(python_translator).translate

        >>> translate("")
        join('',)
        
        """

        if escape is not None:
            string = string.rstrip(escape)
            
        parts = self.split(string)
        if escape is not None:
            parts = map(
                lambda part: isinstance(part, types.expression) and \
                part or self._unescape(part, escape), parts)

        return types.join(parts)            

    def _unescape(self, string, symbol):
        """
        >>> unescape = StringTranslator(None)._unescape
        
        >>> unescape('string:Hello World', ';')
        'string:Hello World'

        >>> unescape('string:Hello World;', ';')
        'string:Hello World;'

        >>> unescape('string:Hello World;;', ';')
        'string:Hello World;'
        
        >>> unescape('; string:Hello World', ';')
        Traceback (most recent call last):
         ...
        SyntaxError: Must escape symbol ';'.

        >>> unescape('; string:Hello World;', ';')
        Traceback (most recent call last):
         ...
        SyntaxError: Must escape symbol ';'.

        >>> unescape('string:Hello; World', ';')
        Traceback (most recent call last):
         ...
        SyntaxError: Must escape symbol ';'.

        >>> unescape(';; string:Hello World', ';')
        '; string:Hello World'
        """

        if re.search("([^%s]|^)%s[^%s]" % (symbol, symbol, symbol), string):
            raise SyntaxError(
                "Must escape symbol %s." % repr(symbol))
        
        return string.replace(symbol+symbol, symbol)

class ImportTranslator(ExpressionTranslator):
    adapts(interfaces.IExpressionTranslator)
    symbol = '_resolve_dotted'
    re_dotted = re.compile(r'^[A-Za-z.]+$')

    def translate(self, string, escape=None):
        """
        >>> import_translator = ImportTranslator()
        >>> resolve_dotted = import_translator.translate

        >>> resolve_dotted("")

        >>> resolve_dotted("chameleon.zpt")
        value("_resolve_dotted('chameleon.zpt')")

        >>> translator = StringTranslator(import_translator)
        >>> translator.tales('import: chameleon.zpt')
        parts(value("_resolve_dotted('chameleon.zpt')"), join('',))

        >>> translator.definitions('zpt import: chameleon.zpt; core import: chameleon.core')
        definitions((declaration('zpt'), parts(value("_resolve_dotted('chameleon.zpt')"), join('',))), (declaration('core'), parts(value("_resolve_dotted('chameleon.core')"), join('',))))

        """

        if not string:
            return None

        string = string.strip()

        if self.re_dotted.match(string) is None:
            raise SyntaxError(string)

        value = types.value("%s('%s')" % (self.symbol, string))
        value.symbol_mapping[self.symbol] = _resolve_dotted
        return value

_module_cache = {}

# stolen from zope.dottedname
def resolve_dotted(name, module=None):
    name = name.split('.')
    if not name[0]:
        if module is None:
            raise ValueError("relative name without base module")
        module = module.split('.')
        name.pop(0)
        while not name[0]:
            module.pop()
            name.pop(0)
        name = module + name

    used = name.pop(0)
    found = __import__(used)
    for n in name:
        used += '.' + n
        try:
            found = getattr(found, n)
        except AttributeError:
            __import__(used)
            found = getattr(found, n)

    return found

def _resolve_dotted(dotted):
    if not dotted in _module_cache:
        resolved = resolve_dotted(dotted)
        _module_cache[dotted] = resolved
    return _module_cache[dotted]


