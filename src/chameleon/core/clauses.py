# -*- coding: utf-8 -*-

from chameleon.core import types
from chameleon.core import config
from chameleon.core import utils

marker = ()

class Assign(object):
    """
    >>> from chameleon.core import testing

    We'll define some values for use in the tests.

    >>> _out, _write, stream = testing.setup_stream()
    >>> one = types.value("1")
    >>> bad_float = types.value("float('abc')")
    >>> abc = types.value("'abc'")
    >>> ghi = types.value("'ghi'")
    >>> exclamation = types.value("'!'")
        
    Simple value assignment:
    
    >>> assign = Assign(one)
    >>> assign.begin(stream, 'a')
    >>> exec stream.getvalue()
    >>> a == 1
    True
    >>> assign.end(stream)
    
    Try-except parts (bad, good):
    
    >>> assign = Assign(types.parts((bad_float, one)))
    >>> assign.begin(stream, 'b')
    >>> exec stream.getvalue()
    >>> b == 1
    True
    >>> assign.end(stream)
    
    Try-except parts (good, bad):
    
    >>> assign = Assign(types.parts((one, bad_float)))
    >>> assign.begin(stream, 'b')
    >>> exec stream.getvalue()
    >>> b == 1
    True
    >>> assign.end(stream)
    
    Join:

    >>> assign = Assign(types.join((abc, ghi)))
    >>> assign.begin(stream, 'b')
    >>> exec stream.getvalue()
    >>> b == 'abcghi'
    True
    >>> assign.end(stream)

    Single join:

    >>> assign = Assign(types.join((abc, )))
    >>> assign.begin(stream, 'b')
    >>> exec stream.getvalue()
    >>> b == 'abc'
    True
    >>> assign.end(stream)

    Join with try-except parts:
    
    >>> assign = Assign(types.join((types.parts((bad_float, abc, ghi)), ghi)))
    >>> assign.begin(stream, 'b')
    >>> exec stream.getvalue()
    >>> b == 'abcghi'
    True
    >>> assign.end(stream)
    """

    def __init__(self, parts, variable=None):
        if not isinstance(parts, types.parts):
            parts = types.parts((parts,))

        self.parts = parts
        self.variable = variable
        
    def begin(self, stream, variable=None):
        """First n - 1 expressions must be try-except wrapped."""

        variable = variable or self.variable
        if isinstance(variable, tuple):
            variable = ", ".join(variable)
            
        for value in self.parts[:-1]:
            stream.write("try:")
            stream.indent()

            self._assign(variable, value, stream)
            
            stream.outdent()
            stream.write("except (%s), e:" % ", ".join(
                exc.__name__ for exc in self.parts.exceptions))
            stream.indent()

        value = self.parts[-1]
        self._assign(variable, value, stream)
        
        stream.outdent(len(self.parts)-1)

    def _assign(self, variable, value, stream):
        stream.annotate(value)
        symbols = stream.symbols.as_dict()
        variable = variable % symbols

        if value.symbol_mapping:
            stream.symbol_mapping.update(value.symbol_mapping)

        if isinstance(value, types.template):
            value = types.value(value % symbols)
        if isinstance(value, types.value):
            stream.write("%s = %s" % (variable, value))
        elif isinstance(value, types.join):
            parts = []
            _v_count = 0

            for part in value:
                if isinstance(part, types.expression):
                    stream.symbol_mapping.update(part.symbol_mapping)
                if isinstance(part, types.template):
                    part = types.value(part % symbols)
                if isinstance(part, (types.parts, types.join)):
                    _v = stream.save()
                    assign = Assign(part, _v)
                    assign.begin(stream)
                    assign.end(stream)
                    _v_count +=1
                    parts.append(_v)
                elif isinstance(part, types.value):
                    parts.append(part)
                elif isinstance(part, unicode):
                    if stream.encoding:
                        parts.append(repr(part.encode(stream.encoding)))
                    else:
                        parts.append(repr(part))
                elif isinstance(part, str):
                    parts.append(repr(part))
                else:
                    raise ValueError("Not able to handle %s" % type(part))

            if len(parts) == 1:
                stream.write("%s = %s" % (variable, "".join(parts)))
            else:
                format = "%s"*len(parts)
                stream.write("%s = '%s' %% (%s)" % (variable, format, ",".join(parts)))

            for i in range(_v_count):
                stream.restore()
        else:
            raise TypeError("Can't assign value of type %s" % type(value))
        
    def end(self, stream):
        pass

class Define(object):
    """
    >>> from chameleon.core import testing

    Variable scope:

    >>> _out, _write, stream = testing.setup_stream()
    >>> define = Define("a", testing.pyexp("b"))
    >>> b = object()
    >>> define.begin(stream)
    >>> exec stream.getvalue()
    >>> a is b
    True
    >>> del a
    >>> define.end(stream)
    >>> exec stream.getvalue()
    >>> a
    Traceback (most recent call last):
        ...
    NameError: name 'a' is not defined
    >>> b is not None
    True

    Multiple defines:

    >>> _out, _write, stream = testing.setup_stream()
    >>> define1 = Define("a", testing.pyexp("b"))
    >>> define2 = Define("c", testing.pyexp("d"))
    >>> d = object()
    >>> define1.begin(stream)
    >>> define2.begin(stream)
    >>> exec stream.getvalue()
    >>> a is b and c is d
    True
    >>> define2.end(stream)
    >>> define1.end(stream)
    >>> del a; del c
    >>> exec stream.getvalue()
    >>> a
    Traceback (most recent call last):
        ...
    NameError: name 'a' is not defined
    >>> c
    Traceback (most recent call last):
        ...
    NameError: name 'c' is not defined
    >>> b is not None and d is not None
    True

    Redefining a variable which is in scope:
    
    >>> _out, _write, stream = testing.setup_stream()
    >>> define1 = Define("a", testing.pyexp("b"))
    >>> define2 = Define("a", testing.pyexp("c"))
    >>> b = object()
    >>> c = object()
    >>> define1.begin(stream)
    >>> define2.begin(stream)
    >>> exec stream.getvalue()
    >>> a is c
    True
    >>> define2.end(stream)
    >>> define1.end(stream)
    >>> del a
    >>> exec stream.getvalue()
    >>> a
    Traceback (most recent call last):
        ...
    NameError: name 'a' is not defined
    
    Tuple assignments:

    >>> _out, _write, stream = testing.setup_stream()
    >>> define = Define(types.declaration(('e', 'f')), testing.pyexp("[1, 2]"))
    >>> define.begin(stream)
    >>> exec stream.getvalue()
    >>> e == 1 and f == 2
    True
    >>> define.end(stream)

    Verify scope is preserved on tuple assignment:

    >>> _out, _write, stream = testing.setup_stream()
    >>> e = None; f = None
    >>> stream.scope[-1].add('e'); stream.scope[-1].add('f')
    >>> stream.scope.append(set())
    >>> define.begin(stream)
    >>> define.end(stream)
    >>> exec stream.getvalue()
    >>> e is None and f is None
    True

    Using semicolons in expressions within a define:

    >>> _out, _write, stream = testing.setup_stream()
    >>> define = Define("a", testing.pyexp("';'"))
    >>> define.begin(stream)
    >>> exec stream.getvalue()
    >>> a
    ';'
    >>> define.end(stream)

    Scope:

    >>> _out, _write, stream = testing.setup_stream()
    >>> a = 1
    >>> stream.scope[-1].add('a')
    >>> stream.scope.append(set())
    >>> define = Define("a", testing.pyexp("2"))
    >>> define.begin(stream)
    >>> define.end(stream)
    >>> exec stream.getvalue()
    >>> a
    1
    """

    assign = None
    
    def __init__(self, declaration, expression=None, dictionary=None):
        if not isinstance(declaration, types.declaration):
            declaration = types.declaration((declaration,))

        if len(declaration) == 1:
            variable = declaration[0]
        else:
            variable = u"(%s,)" % ", ".join(declaration)

        if declaration.global_scope and dictionary is not None:
           variable = "%s['%s'] = %s" % (dictionary, variable, variable)

        if expression is not None:
            self.assign = Assign(expression, variable)

        self.declaration = declaration
        self.dictionary = dictionary

    def begin(self, stream):
        if self.declaration.global_scope:
            # if the declaration belongs to a global scope, remove this
            # symbol from previous scopes
            for scope in stream.scope[1:]:
                for variable in self.declaration:
                    if variable in scope:
                        scope.remove(variable)
                stream.scope[1].add(variable)
        else:
            # save local variables already in in scope
            for var in self.declaration:

                # if we didn't set the variable in this scope already
                if var not in stream.scope[-1]:

                    # we'll check if it's set in one of the older
                    # scopes, e.g. if a backup is at all required
                    for scope in stream.scope[1:-1]:
                        if var in scope:
                            # in which case we back it up to a custom variable name
                            stream.write('%s%d = %s' % (
                                stream.symbols.tmp+var, stream.indentation, var))

                    stream.scope[-1].add(var)

        if self.assign is not None:
            self.assign.begin(stream)

    def end(self, stream):
        if self.assign is not None:
            self.assign.end(stream)

        if not self.declaration.global_scope:
            # restore the variables that were previously in scope
            for var in reversed(self.declaration):
                # if we set the variable in this scope already
                if var in stream.scope[-1]:
                    # we'll check if it's set in one of the older scopes
                    for scope in stream.scope[1:-1]:
                        if var in scope:
                            # in which case we restore it
                            stream.write('%s = %s%d' % (
                                var, stream.symbols.tmp+var, stream.indentation))
                            break
                    else:
                        stream.write("del %s" % var)
                    stream.scope[-1].remove(var)
                            
class Condition(object):
    """
    >>> from chameleon.core import testing, etree

    Unlimited scope:

    >>> _out, _write, stream = testing.setup_stream()
    >>> _validate = utils.validate
    >>> true = Condition(testing.pyexp("True"))
    >>> false = Condition(testing.pyexp("False"))
    >>> true.begin(stream)
    >>> stream.write("print 'Hello'")
    >>> true.end(stream)
    >>> false.begin(stream)
    >>> stream.write("print 'Universe!'")
    >>> false.end(stream)
    >>> stream.write("print 'World!'")
    >>> exec stream.getvalue()
    Hello
    World!

    Finalized limited scope:

    >>> _out, _write, stream = testing.setup_stream()
    >>> true = Condition(testing.pyexp("True"), [Write(testing.pyexp("'Hello'"))])
    >>> false = Condition(testing.pyexp("False"), [Write(testing.pyexp("'Hallo'"))])
    >>> true.begin(stream)
    >>> true.end(stream)
    >>> false.begin(stream)
    >>> false.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    'Hello'

    Open limited scope:

    >>> _out, _write, stream = testing.setup_stream()
    >>> true = Condition(testing.pyexp("True"), [Tag('div')], finalize=False)
    >>> false = Condition(testing.pyexp("False"), [Tag('span')], finalize=False)
    >>> true.begin(stream)
    >>> stream.out("Hello World!")
    >>> true.end(stream)
    >>> false.begin(stream)
    >>> false.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    '<div>Hello World!</div>'

    """
      
    def __init__(self, value, clauses=None, finalize=True, invert=False):
        self.assign = Assign(value)
        self.clauses = clauses
        self.finalize = finalize
        self.invert = invert

    def begin(self, stream):
        temp = stream.save()
        self.assign.begin(stream, temp)

        if self.invert:
            stream.write("if not (%s):" % temp)
        else:
            stream.write("if %s:" % temp)

        stream.indent()
        stream.write("pass")
        
        if self.clauses:
            for clause in self.clauses:
                clause.begin(stream)
            if self.finalize:
                for clause in reversed(self.clauses):
                    clause.end(stream)
                stream.restore()
            stream.outdent()
        elif self.finalize:
            stream.restore()
            
    def end(self, stream):
        if self.clauses:
            if not self.finalize:
                temp = stream.restore()
                if self.invert:
                    stream.write("if not (%s):" % temp)
                else:
                    stream.write("if %s:" % temp)
                stream.indent()
                stream.write("pass")
                for clause in reversed(self.clauses):
                    clause.end(stream)
                    stream.outdent()
        else:
            if not self.finalize:
                stream.restore()
            stream.outdent()
        self.assign.end(stream)

class Else(object):
    def __init__(self, clauses=None):
        self.clauses = clauses
        
    def begin(self, stream):
        stream.write("else:")
        stream.indent()
        stream.write("pass")
        if self.clauses:
            for clause in self.clauses:
                clause.begin(stream)
            for clause in reversed(self.clauses):
                clause.end(stream)
            stream.outdent()
        
    def end(self, stream):
        if not self.clauses:
            stream.outdent()

class Group(object):
    def __init__(self, clauses):
        self.clauses = clauses
        
    def begin(self, stream):
        for clause in self.clauses:
            clause.begin(stream)
        for clause in reversed(self.clauses):
            clause.end(stream)

    def end(self, stream):
        pass

class Visit(object):
    def __init__(self, node):
        self.node = node
        
    def begin(self, stream):
        self.node.visit()

    def end(self, stream):
        pass

class Tag(object):
    """
    >>> from chameleon.core import testing

    Dynamic attribute:

    >>> _out, _write, stream = testing.setup_stream()
    >>> _default = object()
    
    >>> tag = Tag('div', dict(alt=testing.pyexp(repr('Hello World!'))))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    '<div alt="Hello World!">Hello Universe!</div>'

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> tag = Tag('div', dict(alt=testing.pyexp(repr('Hello World!'))))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    u'<div alt="Hello World!">Hello Universe!</div>'

    Cancelling attribute via false value:

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> tag = Tag('div', dict(alt=testing.pyexp(None)))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    '<div>Hello Universe!</div>'

    Escaping of <, >, & and double quotes

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> tag = Tag('div', dict(alt=testing.pyexp(repr('<>&"'))))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    u'<div alt="&lt;&gt;&amp;&quot;">Hello Universe!</div>'

    Attribute default value is available under the `default` symbol.

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> tag = Tag('div', dict(alt=testing.pyexp('default')),
    ...     defaults=dict(alt='Hello World!'))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    u'<div alt="Hello World!">Hello Universe!</div>'

    Verify that unicode data is handled correctly.

    >>> _out, _write, stream = testing.setup_stream()
    >>> tag = Tag('div', dict(
    ...     alt=testing.pyexp(repr(unicode('La Pe\xc3\xb1a', 'utf-8')))))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> 'Hello' in _out.getvalue()
    True

    Dictionary attributes:

    >>> _out, _write, stream = testing.setup_stream()
    >>> tag = Tag('div', expression=testing.pyexp(repr({'alt': 'Hello World!'})))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    '<div alt="Hello World!">Hello Universe!</div>'
    
    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> tag = Tag('div', expression=testing.pyexp(repr({'alt': 'Hello World!'})))
    >>> tag.begin(stream)
    >>> stream.out('Hello Universe!')
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    u'<div alt="Hello World!">Hello Universe!</div>'

    Self-closing tag:

    >>> _out, _write, stream = testing.setup_stream()
    >>> tag = Tag('br', {}, True)
    >>> tag.begin(stream)
    >>> tag.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    '<br />'
    """

    def __init__(self, tag, attributes=None, selfclosing=False,
                 expression=None, cdata=False, defaults={}):
        """Render tag.

        Note that ``attributes`` must be rendered in order, except if
        they're replaced by the attributes dictionary in the evaluated
        ``expression``.
        """
        
        self.tag = tag
        self.defaults = defaults
        self.selfclosing = selfclosing
        self.attributes = attributes or {}
        self.expression = expression and Assign(expression)
        self.cdata = cdata
        
    def begin(self, stream):
        if self.cdata:
            stream.out('<![CDATA['); return

        stream.out('<%s' % self.tag)

        temp = stream.save()
        temp2 = stream.save()
        
        if self.expression:
            self.expression.begin(stream, stream.symbols.tmp)
            # loop over all attributes
            stream.write("for %s, %s in %s.items():" % \
                         (temp, temp2, stream.symbols.tmp))
            stream.indent()

            # only include attribute if expression is not None
            stream.write("if %s is not None:" % temp2)
            stream.indent()

            # if an encoding is specified, we need to check
            # whether we're dealing with unicode strings or not,
            # before writing out the attribute
            stream.ensure_unicode(temp2)

            # escape expression
            stream.escape(temp2, escape_double_quote=True)

            # write out attribute
            stream.out(types.value(
                "' %%s=\"%%s\"' %% (%s, %s)" % (temp, temp2)))

            stream.outdent()
            stream.outdent()

        for attribute, value in self.attributes.items():
            if isinstance(value, types.expression):
                # as an optimization, we only define the `default` symbol,
                # if it's present in the evaluation value (as string
                # representation).
                if stream.symbols.default in repr(value):
                    default = self.defaults.get(attribute, marker)
                else:
                    default = None

                if default is marker:
                    stream.write("%s = %s" % (
                        stream.symbols.default,
                        stream.symbols.default_marker_symbol))
                elif default is not None:
                    stream.write("%s = %s" % (stream.symbols.default, repr(default)))

                assign = Assign(value)
                assign.begin(stream, temp)

                if default is not None:
                    stream.write("%s = None" % stream.symbols.default)

                # verify that attribute value is not the default marker
                stream.write("if %s is %s:" % (
                    temp, stream.symbols.default_marker_symbol))
                default_string = self.defaults.get(attribute)
                stream.indent()
                stream.write("%s = %s" % (
                    temp, repr(default_string)))
                stream.outdent()

                stream.write("if %s is None or %s is False:" % (temp, temp))
                stream.indent()
                stream.write("pass")
                stream.outdent()
                stream.write("else:")
                stream.indent()

                # if an encoding is specified, we need to check
                # whether we're dealing with unicode strings or not,
                # before writing out the attribute
                stream.ensure_unicode(temp)

                # escape expression
                stream.escape(temp, escape_double_quote=True)

                # print attribute
                stream.out(types.value(
                    "' %s=\"'+%s+'\"'" % (
                    attribute, temp)))

                stream.outdent()
                assign.end(stream)
            else:
                # escape expression
                value = utils.escape(value, '"', 'ascii')

                # if there are dynamic expressions, we only want to write
                # out static attributes if they're not in the dynamic
                # expression dictionary
                if self.expression:
                    stream.write("if '%s' not in %s:" % (
                        attribute, stream.symbols.tmp))
                    stream.indent()

                stream.out(' %s="%s"' % (attribute, value))

                if self.expression:
                    stream.outdent()

        stream.restore()
        stream.restore()

        if self.selfclosing:
            stream.out(" />")
        else:
            stream.out(">")

    def end(self, stream):
        if self.cdata:
            stream.out(']]>'); return
            
        if not self.selfclosing:
            stream.out('</%s>' % self.tag)

class Repeat(object):
    """
    >>> from chameleon.core import testing

    We need to set up the repeat object.

    >>> from chameleon.core import utils
    >>> repeat = utils.repeatdict()

    Simple repeat loop and repeat data structure:

    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("i",)), testing.pyexp("range(5)"))
    >>> _repeat.begin(stream)
    >>> stream.write("r = repeat['i']")
    >>> stream.write(
    ...     "print (i, r.index, r.letter(), r.Letter(), r.roman(), r.Roman(), r.start, r.end, r.number(), r.odd(), r.even())")
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()
    (0, 0, 'a', 'A', 'i', 'I', True, False, 1, '', 'even')
    (1, 1, 'b', 'B', 'ii', 'II', False, False, 2, 'odd', '')
    (2, 2, 'c', 'C', 'iii', 'III', False, False, 3, '', 'even')
    (3, 3, 'd', 'D', 'iv', 'IV', False, False, 4, 'odd', '')
    (4, 4, 'e', 'E', 'v', 'V', False, True, 5, '', 'even')
    >>> _repeat.end(stream)

    A repeat over an empty set.

    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("j",)), testing.pyexp("range(0)"))
    >>> _repeat.begin(stream)
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()

    A tuple repeat over an empty set.

    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("j", "k")),
    ...      testing.pyexp("range(0)"), repeatdict=False)
    >>> _repeat.begin(stream)
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()

    A tuple repeat

    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("l", "m")),
    ...      testing.pyexp("zip(range(3), range(3))"), repeatdict=False)
    >>> _repeat.begin(stream)
    >>> stream.write("print l, m")
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()
    0 0
    1 1
    2 2
    
    A repeat over an iterable which has no length, renders the generator.

    >>> class iterator(object):
    ...     def __iter__(self):
    ...         yield 1; yield 2; yield 3
    
    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("i",)), testing.pyexp("iterator()"))
    >>> _repeat.begin(stream)
    >>> stream.write("r = repeat['i']")
    >>> stream.write(
    ...     "print (i, r.index, r.start, r.end, r.number(), r.odd(), r.even())")
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()
    (1, 0, True, False, 1, '', 'even')
    (2, 1, False, False, 2, 'odd', '')
    (3, 2, False, True, 3, '', 'even')
    >>> _repeat.end(stream)

    A repeat over a non-iterable raises an exception.

    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("j",)), testing.pyexp("object()"))
    >>> _repeat.begin(stream)
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()
    Traceback (most recent call last):
     ...
    TypeError: 'object' object is not iterable

    Repeating over ``None`` is equal to repeating over the empty tuple.

    >>> _out, _write, stream = testing.setup_stream()
    >>> _repeat = Repeat(types.declaration(("j",)), testing.pyexp("None"))
    >>> _repeat.begin(stream)
    >>> _repeat.end(stream)
    >>> exec stream.getvalue()

    Simple for loop:
  
    >>> _out, _write, stream = testing.setup_stream()
    >>> _for = Repeat(types.declaration(("i",)),
    ...     testing.pyexp("range(3)"), repeatdict=False)
    >>> _for.begin(stream)
    >>> stream.write("print i")
    >>> _for.end(stream)
    >>> exec stream.getvalue()
    0
    1
    2
    >>> _for.end(stream)

    """

    def __init__(self, declaration, value, scope=(), repeatdict=True, newline=True):
        if len(declaration) > 1:
            assert repeatdict is False

        self.declaration = declaration            
        self.define = Define(declaration)
        self.assign = Assign(value)
        self.repeatdict = repeatdict
        self.newline = newline
        
    def begin(self, stream):
        # initialize variable scope
        self.define.begin(stream)

        # assign iterator
        iterator = stream.save()
        length = stream.save()
        self.assign.begin(stream, iterator)

        # initialize variables
        stream.write("%s = %s" % (
            ", ".join(self.declaration),
            ", ".join((repr(None),)*len(self.declaration))))
        
        if self.repeatdict:
            variable = self.declaration[0]
            assert ',' not in variable
            stream.write("%s, %s = repeat.insert('%s', %s)" % (
                iterator, length, variable, iterator))
            stream.write("for %s in %s:" % (
                variable, iterator))
        else:
            stream.write("%s = tuple(%s)" % (iterator, iterator))
            stream.write("%s = len(%s)" % (length, iterator))
            stream.write("for %s in %s:" % (
                ", ".join(self.declaration), iterator))
        stream.indent()
        stream.write("%s = %s - 1" % (length, length))

    def end(self, stream):
        length = stream.restore()
        iterator = stream.restore()

        stream.write("if %s == 0:" % length)
        stream.indent()
        stream.write("break")
        stream.outdent()

        if self.newline:
            stream.out('\n')
        else:
            stream.out(' ')
        stream.outdent()

        self.assign.end(stream)
        self.define.end(stream)

class Write(object):
    """
    >>> from chameleon.core import testing, etree

    Basic write:

    >>> _out, _write, stream = testing.setup_stream()
    >>> _validate = utils.validate
    >>> write = Write(testing.pyexp("'New York'"))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    'New York'

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> write = Write(testing.pyexp("'New York'"))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    u'New York'

    Try-except parts:

    >>> _out, _write, stream = testing.setup_stream()
    >>> write = Write(testing.pyexp('undefined', '"New Delhi"'))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    'New Delhi'

    Unicode:

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> write = Write(types.value(repr('La Pe\xc3\xb1a'.decode('utf-8'))))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> val = _out.getvalue()
    >>> val == u'La Pe\xf1a'
    True
    >>> isinstance(val, unicode)
    True

    Object that offers an ``__html__`` method:

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> class Markup(unicode):
    ...     def __html__(self): return self
    >>> data = Markup("one & two")
    >>> write = Write(
    ...    types.escape(types.value('data')))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    u'one & two'
    """

    assign = None
    
    def __init__(self, value, defer=False):
        self.assign = Assign(value)
        self.structure = not isinstance(value, types.escape)
        self.defer = defer
        
    def begin(self, stream):
        if not self.defer:
            self.write(stream)
            
    def end(self, stream):
        if self.defer:
            self.write(stream)
    
    def write(self, stream):
        temp = stream.save()
        symbols = stream.symbols.as_dict()

        def write(template):
            stream.write(template % symbols)

        self.assign.begin(stream, temp)
        expr = temp

        stream.write("%s = %s" % (stream.symbols.tmp, expr))
        write("if %(tmp)s.__class__ not in (str, unicode, int, float) and hasattr(%(tmp)s, '__html__'):")
        stream.indent()
        stream.out(types.value("%s.__html__()" % symbols['tmp']))
        stream.outdent()
        
        write("elif %(tmp)s is not None:")
        stream.indent()

        stream.ensure_unicode(stream.symbols.tmp)

        # escape non-structural values
        if not self.structure:
            stream.escape(stream.symbols.tmp)

        stream.out(types.value(symbols['tmp']))
        stream.outdent()

        # validate XML if enabled
        if config.VALIDATION:
            try:
                _et = utils.import_elementtree()
            except ImportError:
                raise ImportError(
                    "ElementTree (required when XML validation is enabled).")

            stream.symbol_mapping[stream.symbols.validate] = utils.validate
            write("%(validate)s(%(tmp)s)")

        self.assign.end(stream)
        stream.restore()

class UnicodeWrite(Write):
    """
    >>> from chameleon.core import testing, etree

    Basic write:

    >>> _out, _write, stream = testing.setup_stream()
    >>> _validate = utils.validate
    >>> write = UnicodeWrite(types.value("'New York'"))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    'New York'

    Unicode:

    >>> _out, _write, stream = testing.setup_stream('utf-8')
    >>> write = UnicodeWrite(types.value(repr(unicode('La Pe\xc3\xb1a', 'utf-8'))))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> val = _out.getvalue()
    >>> val == u'La Pe\xf1a'
    True
    >>> type(val) == unicode
    True

    Invalid:

    >>> _out, _write, stream = testing.setup_stream()
    >>> write = UnicodeWrite(types.value("None"))
    >>> write.begin(stream)
    >>> write.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    ''
    """

    def write(self, stream):
        temp = stream.save()
        self.assign.begin(stream, temp)
        stream.out(types.value(temp))
        self.assign.end(stream)
        stream.restore()

class Out(object):
    """
    >>> from chameleon.core import testing
      
    >>> _out, _write, stream = testing.setup_stream()
    >>> out = Out('Hello World!')
    >>> out.begin(stream)
    >>> out.end(stream)
    >>> exec stream.getvalue()
    >>> _out.getvalue()
    'Hello World!'
    """
    
    def __init__(self, string, defer=False):
        self.string = string
        self.defer = defer

    def begin(self, stream):
        if not self.defer:
            stream.out(self.string)
        
    def end(self, stream):
        if self.defer:
            stream.out(self.string)

class Callback(object):
    """Callback method for an element visitor."""

    def __init__(self, name, visitor, args, newline):
        self.name = name
        self.visitor = visitor
        self.args = args
        self.newline = newline
        
    def begin(self, stream):
        stream.write("def %s(%s, %s, **_ignored):" % (
            self.name, stream.symbols.scope, self.args))
        stream.indent()
        stream.write("pass")
        
        # visit slot node
        self.visitor.begin(stream)
        self.visitor.end(stream)

        if self.newline:
            stream.out('\n')
            
        stream.outdent()
        
    def end(self, stream):
        pass

class Slot(object):
    """Call slot, updating """

    def __init__(self, expression, scope_args):
        self.expression = expression
        self.scope_args = scope_args

    def begin(self, stream):
        stream.write("%s.update(dict(%s))" % (
            stream.symbols.scope,
            ", ".join("%s=%s" % (arg, arg) for arg in self.scope_args)))

        value = self.expression
        if isinstance(value, types.template):
            symbols = stream.symbols.as_dict()
            value = types.value(value % symbols)

        stream.write(value)

    def end(self, stream):
        pass

class Macro(object):
    """Use macro."""

    def __init__(self, slots, args, extend=False, extend_except=None, label=None):
        self.assign = Assign(slots)
        self.extend = extend
        self.extend_except = extend_except
        self.args = args
        self.label = label

    def begin(self, stream):
        self.assign.begin(stream, stream.symbols.tmp)

        if self.extend:
            stream.write("for _name in %s:" % stream.symbols.slots)
            stream.indent()
            if self.extend_except:
                stream.write("if _name not in %s and _name not in (%s,):" % (
                    stream.symbols.tmp, ", ".join(map(repr, self.extend_except))))
            else:
                stream.write("if _name not in %s:" % stream.symbols.tmp)

            stream.indent()
            stream.write("%s[_name] = %s[_name]" % (
                stream.symbols.tmp, stream.symbols.slots))
            stream.outdent()
            stream.outdent()

        stream.annotate(self.label)
        stream.write("%s.render(%s, %s)" % (
            stream.symbols.metal, stream.symbols.tmp, self.args))

    def end(self, stream):
        self.assign.end(stream)
        
class Method(object):
    """
    >>> from chameleon.core import testing
      
    >>> _out, _write, stream = testing.setup_stream()
    >>> econtext = {}
    >>> method = Method('test', ('a', 'b', 'c'))
    >>> method.begin(stream)
    >>> stream.write('print a, b, c')
    >>> method.end(stream)
    >>> exec stream.getvalue()
    >>> test(1, 2, 3)
    1 2 3
      
    """

    ret = None
    
    def __init__(self, name, args, ret=None, decorators=(), dictionary=None):
        self.name = name
        self.args = args
        self.decorators = decorators
        self.dictionary = dictionary
        
        if ret is not None:
            self.ret = Assign(ret, '_ret')

    def begin(self, stream):
        for decorator in self.decorators:
            stream.write("@%s" % decorator)
        stream.write('def %s(%s):' % (self.name, ", ".join(self.args)))
        stream.indent()

    def end(self, stream):
        if self.ret is not None:
            self.ret.begin(stream)
            stream.write('return _ret')
            self.ret.end(stream)
        
        stream.outdent()

        if self.dictionary is not None:
            assign = Assign(
                types.value(self.name), "%s['%s']" % \
                (self.dictionary, self.name))
            assign.begin(stream)
            assign.end(stream)
