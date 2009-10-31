from compiler import ast

class ASTTransformer(object):
    """General purpose base class for AST transformations.
    
    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """

    def visit(self, node):
        if node is None:
            return None
        if isinstance(node, (tuple, list)):
            return tuple(self.visit(n) for n in node)
        visitor = getattr(self, 'visit%s' % node.__class__.__name__,
                          self._visitDefault)
        return visitor(node)

    def _clone(self, node, *args):
        lineno = getattr(node, 'lineno', None)
        node = node.__class__(*args)
        if lineno is not None:
            node.lineno = lineno
        if isinstance(node, (ast.Class, ast.Function, ast.GenExpr, ast.Lambda)):
            node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def _visitDefault(self, node):
        return node

    def visitExpression(self, node):
        return self._clone(node, self.visit(node.node))

    def visitModule(self, node):
        return self._clone(node, node.doc, self.visit(node.node))

    def visitStmt(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    # Classes, Functions & Accessors

    def visitCallFunc(self, node):
        return self._clone(node, self.visit(node.node),
            [self.visit(x) for x in node.args],
            node.star_args and self.visit(node.star_args) or None,
            node.dstar_args and self.visit(node.dstar_args) or None
        )

    def visitClass(self, node):
        return self._clone(node, node.name, [self.visit(x) for x in node.bases],
            node.doc, self.visit(node.code)
        )

    def visitFunction(self, node):
        args = []
        if hasattr(node, 'decorators'):
            args.append(self.visit(node.decorators))
        return self._clone(node, *args + [
            node.name,
            node.argnames,
            [self.visit(x) for x in node.defaults],
            node.flags,
            node.doc,
            self.visit(node.code)
        ])

    def visitGetattr(self, node):
        return self._clone(node, self.visit(node.expr), node.attrname)

    def visitLambda(self, node):
        node = self._clone(node, node.argnames,
            [self.visit(x) for x in node.defaults], node.flags,
            self.visit(node.code)
        )
        return node

    def visitSubscript(self, node):
        return self._clone(node, self.visit(node.expr), node.flags,
            [self.visit(x) for x in node.subs]
        )

    # Statements

    def visitAssert(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.fail))

    def visitAssign(self, node):
        expr = self.visit(node.expr)
        return self._clone(
            node, [self.visit(x) for x in node.nodes], expr)

    def visitAssAttr(self, node):
        return self._clone(node, self.visit(node.expr), node.attrname,
            node.flags
        )

    def visitAugAssign(self, node):
        return self._clone(node, self.visit(node.node), node.op,
            self.visit(node.expr)
        )

    def visitDecorators(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    def visitExec(self, node):
        return self._clone(node, self.visit(node.expr), self.visit(node.locals),
            self.visit(node.globals)
        )

    def visitFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.list),
            self.visit(node.body), self.visit(node.else_)
        )

    def visitIf(self, node):
        return self._clone(node, [self.visit(x) for x in node.tests],
            self.visit(node.else_)
        )

    def _visitPrint(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes],
            self.visit(node.dest)
        )
    visitPrint = visitPrintnl = _visitPrint

    def visitRaise(self, node):
        return self._clone(node, self.visit(node.expr1), self.visit(node.expr2),
            self.visit(node.expr3)
        )

    def visitReturn(self, node):
        return self._clone(node, self.visit(node.value))

    def visitTryExcept(self, node):
        return self._clone(node, self.visit(node.body), self.visit(node.handlers),
            self.visit(node.else_)
        )

    def visitTryFinally(self, node):
        return self._clone(node, self.visit(node.body), self.visit(node.final))

    def visitWhile(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.body),
            self.visit(node.else_)
        )

    def visitWith(self, node):
        return self._clone(node, self.visit(node.expr),
            [self.visit(x) for x in node.vars], self.visit(node.body)
        )

    def visitYield(self, node):
        return self._clone(node, self.visit(node.value))

    # Operators

    def _visitBoolOp(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])
    visitAnd = visitOr = visitBitand = visitBitor = visitBitxor = _visitBoolOp
    visitAssTuple = visitAssList = _visitBoolOp

    def _visitBinOp(self, node):
        return self._clone(node,
            (self.visit(node.left), self.visit(node.right))
        )
    visitAdd = visitSub = _visitBinOp
    visitDiv = visitFloorDiv = visitMod = visitMul = visitPower = _visitBinOp
    visitLeftShift = visitRightShift = _visitBinOp

    def visitCompare(self, node):
        return self._clone(node, self.visit(node.expr),
            [(op, self.visit(n)) for op, n in  node.ops]
        )

    def _visitUnaryOp(self, node):
        return self._clone(node, self.visit(node.expr))
    visitUnaryAdd = visitUnarySub = visitNot = visitInvert = _visitUnaryOp
    visitBackquote = visitDiscard = _visitUnaryOp

    def visitIfExp(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.then),
            self.visit(node.else_)
        )

    # Identifiers, Literals and Comprehensions

    def visitDict(self, node):
        return self._clone(node, 
            [(self.visit(k), self.visit(v)) for k, v in node.items]
        )

    def visitGenExpr(self, node):
        return self._clone(node, self.visit(node.code))

    def visitGenExprFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.iter),
            [self.visit(x) for x in node.ifs]
        )

    def visitGenExprIf(self, node):
        return self._clone(node, self.visit(node.test))

    def visitGenExprInner(self, node):
        quals = [self.visit(x) for x in node.quals]
        return self._clone(node, self.visit(node.expr), quals)

    def visitKeyword(self, node):
        return self._clone(node, node.name, self.visit(node.expr))

    def visitList(self, node):
        return self._clone(node, [self.visit(n) for n in node.nodes])

    def visitListComp(self, node):
        quals = [self.visit(x) for x in node.quals]
        return self._clone(node, self.visit(node.expr), quals)

    def visitListCompFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.list),
            [self.visit(x) for x in node.ifs]
        )

    def visitListCompIf(self, node):
        return self._clone(node, self.visit(node.test))

    def visitSlice(self, node):
        return self._clone(node, self.visit(node.expr), node.flags,
            node.lower and self.visit(node.lower) or None,
            node.upper and self.visit(node.upper) or None
        )

    def visitSliceobj(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    def visitTuple(self, node):
        return self._clone(node, [self.visit(n) for n in node.nodes])
