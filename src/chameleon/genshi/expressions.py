import re
import parser

from chameleon.core import types
from chameleon.core import parsing

class ExpressionTranslator(object):
    """Genshi expression translation."""

    re_method = re.compile(r'^(?P<name>[A-Za-z0-9_]+)'
                           '(\((?P<args>[A-Za-z0-9_]+\s*(,\s*[A-Za-z0-9_]+)*)\))?')


    def declaration(self, string):
        """Variable declaration.

        >>> declaration = ExpressionTranslator().declaration

        Single variable:

        >>> declaration("variable")
        declaration('variable')

        Multiple variables:

        >>> declaration("variable1,variable2")
        declaration('variable1', 'variable2')

        >>> declaration("variable1, variable2")
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

            while '  ' in d:
                d = d.replace('  ', ' ')

            parts = d.split(' ')
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
        ...     def validate(self, string):
        ...         if string == '' or ';' in string:
        ...             raise SyntaxError()
        ...
        ...     def translate(self, string):
        ...         return types.value(string.strip())
        
        >>> definitions = MockExpressionTranslator().definitions
        
        Single define:
        
        >>> definitions("variable expression")
        definitions((declaration('variable'), value('expression')),)
        
        Multiple defines:
        
        >>> definitions("variable1 expression1; variable2 expression2")
        definitions((declaration('variable1'), value('expression1')),
                    (declaration('variable2'), value('expression2')))
        
        Tuple define:
        
        >>> definitions("(variable1, variable2) (expression1, expression2)")
        definitions((declaration('variable1', 'variable2'),
                    value('(expression1, expression2)')),)

        Space, the 'in' operator and '=' may be used to separate
        variable from expression.

        >>> definitions("variable in expression")
        definitions((declaration('variable'), value('expression')),)        

        >>> definitions("(variable1,variable2, variable3) in expression")
        definitions((declaration('variable1', 'variable2', 'variable3'),
        value('expression')),)        

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
        global_scope = False
        
        while i < len(string):
            while string[i] == ' ':
                i += 1

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
                expr = self.expression(string[i:])
                j = -1
            except SyntaxError, e:
                expr = None
                j = len(string)
            
            while j > i:
                j = string.rfind(';', i, j)
                if j < 0:
                    raise e

                try:
                    expr = self.expression(string[i:j])
                except SyntaxError, e:
                    if string.rfind(';', i, j) > 0:
                        continue
                    raise e
                
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
        ...     def validate(self, string):
        ...         return True
        ...
        ...     def translate(self, string):
        ...         return types.value(string)

        >>> output = MockExpressionTranslator().output

        >>> output("context/title")
        escape(value('context/title'),)

        >>> output("structure context/title")
        value('context/title')        
        """
        
        if string.startswith('structure '):
            return self.expression(string[len('structure')+1:])
        
        expression = self.expression(string)

        if isinstance(expression, types.parts):
            return types.escape(expression)

        return types.escape((expression,))
            
    def expression(self, string):
        self.validate(string)
        return self.translate(string)

    def method(self, string):
        """Parse a method definition.

        >>> method = ExpressionTranslator().method

        >>> method('name')
        name()

        >>> method('name(a, b, c)')
        name(a, b, c)

        """

        m = self.re_method.match(string)
        if m is None:
            raise ValueError("Not a valid method definition (%s)." % string)

        name = m.group('name')
        args = [arg.strip() for arg in (m.group('args') or "").split(',') if arg]

        return types.method(name, args)

    def validate(self, string):
        """We use the ``parser`` module to determine if
        an expression is a valid python expression."""

        if isinstance(string, unicode):
            string = string.encode('utf-8')

        if string != "":
            parser.expr(string.strip())

    def translate(self, string):
        if isinstance(string, str):
            string = string.decode('utf-8')

        return types.value(string.strip())

    def split(self, string):
        return parsing.interpolate(string, self.expression)

translator = ExpressionTranslator()
