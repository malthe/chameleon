import sys
import __builtin__

from chameleon.ast.astutil import parse
from chameleon.ast.astutil import _ast as ast
from chameleon.ast.astutil import ASTTransformer
from chameleon.ast.astutil import ASTCodeGenerator
from chameleon.core import config

CONSTANTS = frozenset(['False', 'True', 'None', 'NotImplemented', 'Ellipsis'])
SYMBOLS = config.SYMBOLS.as_dict().values()
UNDEFINED = object()
OP_IGNORE = 'OP_IGNORE'

def flatten(list):
    """Flattens a potentially nested sequence into a flat list.
    """
    l = []
    for elt in list:
        t = type(elt)
        if t is set or t is tuple or t is list or t is frozenset:
            for elt2 in flatten(elt):
                l.append(elt2)
        else:
            l.append(elt)
    return l

def lookup_attr(obj, key):
    try:
        return getattr(obj, key)
    except AttributeError, e:
        try:
            get = obj.__getitem__
        except AttributeError:
            raise e
        try:
            return get(key)
        except KeyError:
            raise e

def lookup_attr_debug(obj, key):
    try:
        cls = obj.__class__
        attr = getattr(cls, key)
        get = getattr(attr, '__get__', None)
    except AttributeError:
        attr = None

    if attr is not None:
        return get(obj, cls)
    else:
        try:
            return getattr(obj, key)
        except AttributeError, e:
            try:
                get = obj.__getitem__
            except AttributeError:
                raise e
            try:
                return get(key)
            except KeyError:
                raise e

class TemplateASTTransformer(ASTTransformer):
    def __init__(self, globals):
        self.locals = [CONSTANTS]
        builtin = dir(__builtin__)
        self.locals.append(set(globals))
        self.locals.append(set(builtin))
        # self.names is an optimization for visitName (so we don't
        # need to flatten the locals every time it's called)
        self.names = set()
        self.names.update(CONSTANTS)
        self.names.update(builtin)
        self.names.update(globals)

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        return ASTTransformer.visit_Assign(self, node)

    def visit_Delete(self, node):
        ASTTransformer.visit_Delete(self, node)

        # drop node
        pass

    def visit_FunctionDef(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
            self.names.add(node.name)

        # process defaults *before* defining parameters
        node.args.defaults = tuple(
            self.visit(x) for x in node.args.defaults)

        if node.args.args:
            argnames = [arg.id for arg in node.args.args]
            self.locals.append(set(argnames))
            argnames = set(argnames)
            newnames = argnames.difference(self.names)
            self.names.update(newnames)

        try:
            return ASTTransformer.visit_FunctionDef(self, node)
        finally:
            if node.args.args:
                self.locals.pop()
                self.names -= newnames

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if node.id not in self.names:
                # this should be spellable as...
                ##                     return ast.Subscript(
                ##                         ast.Name("econtext", ast.Load()),
                ##                         ast.Index(ast.Str(node.id)),
                ##                         ast.Load())
                ## .. but Python 2.5 doesn't allow it.
                name = ast.Name()
                name.id = 'econtext'
                name.ctx = ast.Load()
                idx = ast.Index()
                idx.value = ast.Str()
                idx.value.s = node.id
                subscr = ast.Subscript()
                subscr.value = name
                subscr.slice = idx
                subscr.ctx = ast.Load()
                return subscr


        if isinstance(node.ctx, (ast.Param, ast.Store)):
            self.locals[-1].add(node.id)
            self.names.add(node.id)

        if isinstance(node.ctx, ast.Del):
            self.locals[-1].remove(node.id)
            self.names.remove(node.id)

        return node

    def visit_ImportFrom(self, node):
        for index, alias in enumerate(node.names):
            if alias.asname is None:
                self.names.add(alias.name)
            else:
                self.names.add(alias.asname)
        return node

    def visit_Attribute(self, node):
        """Get attribute with fallback to dictionary lookup.

        Note: Variables starting with an underscore are exempt
        (reserved for internal use); as are the default system symbols.
        """

        if isinstance(node.value, ast.Name) and \
           (node.value.id.startswith('_') or node.value.id in SYMBOLS):
            return ASTTransformer.visit_Attribute(self, node)

        ## This should be spellable as
        ##         return ast.Call(
        ##             ast.Name(config.SYMBOLS.lookup_attr, ast.Load()),
        ##             [self.visit(node.value), ast.Str(node.attr)],
        ##             [], None, None)
        ## .. except Python 2.5 doesn't allow it.

        call = ast.Call()
        name = ast.Name()
        name.id = config.SYMBOLS.lookup_attr
        name.ctx = ast.Load()
        call.func = name
        string = ast.Str()
        string.s = node.attr
        args = [self.visit(node.value), string]
        call.args = args
        call.keywords = []
        call.starargs = None
        call.kwargs = None
        return call

    def visit_arguments(self, node):
        node.args = [self.visit(arg) for arg in node.args]
        return node

    def visit_Lambda(self, node):
        self.locals.append(set())
        try:
            return super(TemplateASTTransformer, self).visit_Lambda(node)
        finally:
            self.locals.pop()

    def visit_ListComp(self, node):
        self.locals.append(set())
        node.generators = [self.visit(gen) for gen in node.generators]
        node = super(TemplateASTTransformer, self).visit_ListComp(node)
        self.locals.pop()
        return node

class Suite(object):
    __slots__ = ['source', '_globals']

    mode = 'exec'

    def __init__(self, source, globals=()):
        """Create the code object from a string."""

        if isinstance(source, unicode):
            source = source.encode('utf-8')

        node = parse(source, self.mode)
        transform = TemplateASTTransformer(globals)
        tree = transform.visit(node)
        generator = ASTCodeGenerator(tree)
        self.source = generator.code

    def __hash__(self):
        return hash(self.source)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.source)
