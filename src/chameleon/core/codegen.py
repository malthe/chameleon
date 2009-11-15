from compiler import ast, parse
from sourcecodegen import ModuleSourceCodeGenerator
from transformer import ASTTransformer
from chameleon.core import config

import __builtin__

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

def lookup_name(data, name):
    try:
        return data[name]
    except KeyError:
        raise NameError(name)
    
lookup_globals = {
    '_lookup_attr': lookup_attr,
    '_lookup_name': lookup_name,
    }       

class TemplateASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.

    """

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

    def visitConst(self, node):
        return node

    def visitAssName(self, node):
        if len(self.locals) > 1:
            if node.flags == 'OP_ASSIGN':
                self.locals[-1].add(node.name)
                self.names.add(node.name)
            else:
                self.locals[-1].remove(node.name)
                self.names.remove(node.name)
                return None
        return node

    def visitClass(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
            self.names.add(node.name)
        self.locals.append(set())
        try:
            return ASTTransformer.visitClass(self, node)
        finally:
            self.locals.pop()

    def visitFor(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitFor(self, node)
        finally:
            self.locals.pop()

    def visitFunction(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
            self.names.add(node.name)

        # process defaults *before* defining parameters
        node.defaults = tuple(self.visit(x) for x in node.defaults)

        self.locals.append(set(node.argnames))
        argnames = set(node.argnames)
        newnames = argnames.difference(self.names)
        self.names.update(newnames)

        try:
            return ASTTransformer.visitFunction(self, node)
        finally:
            self.locals.pop()
            self.names -= newnames
            
    def visitGenExpr(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitGenExpr(self, node)
        finally:
            self.locals.pop()

    def visitLambda(self, node):
        argnames = flatten(node.argnames)
        self.names.update(argnames)
        self.locals.append(set(argnames))
        try:
            return ASTTransformer.visitLambda(self, node)
        finally:
            self.locals.pop()

    def visitListComp(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitListComp(self, node)
        finally:
            self.locals.pop()

    def visitName(self, node):
        if not node.name in self.names:
            return ast.Subscript(
                ast.Name("econtext"), None, [ast.Const(node.name)])
        return node

    def visitFrom(self, node):
        for index, (name, alias) in enumerate(node.names):
            if alias is None:
                self.names.add(name)
            else:
                self.names.add(alias)            
        return node

    def visitGetattr(self, node):
        """Get attribute with fallback to dictionary lookup.

        Note: Variables starting with an underscore are exempt
        (reserved for internal use); as are the default system symbols.
        """
        
        if hasattr(node.expr, 'name') and node.expr.name.startswith('_') or \
               isinstance(node.expr, ast.Name) and node.expr.name in SYMBOLS:
            return ASTTransformer.visitGetattr(self, node)

        return ast.CallFunc(ast.Name('_lookup_attr'), [
            self.visit(node.expr), ast.Const(node.attrname)
            ])

class Suite(object):
    __slots__ = ['source', '_globals']

    mode = 'exec'
    
    def __init__(self, source, globals=()):
        """Create the code object from a string."""

        if isinstance(source, unicode):
            source = source.encode('utf-8')
            
        node = parse(source, self.mode)
        
        # build tree
        transform = TemplateASTTransformer(globals)
        tree = transform.visit(node)
        filename = tree.filename = '<script>'

        # generate source code
        self.source = ModuleSourceCodeGenerator(tree).getSourceCode()
        
    def __hash__(self):
        return hash(self.source)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.source)
