# -*- coding: utf-8 -*-
#
# Copyright 2008 by Armin Ronacher.
# License: Python License.
#

import _ast

from _ast import *


def fix_missing_locations(node):
    """
    When you compile a node tree with compile(), the compiler expects lineno and
    col_offset attributes for every node that supports them.  This is rather
    tedious to fill in for generated nodes, so this helper adds these attributes
    recursively where not already set, by setting them to the values of the
    parent node.  It works recursively starting at *node*.
    """
    def _fix(node, lineno, col_offset):
        if 'lineno' in node._attributes:
            if not hasattr(node, 'lineno'):
                node.lineno = lineno
            else:
                lineno = node.lineno
        if 'col_offset' in node._attributes:
            if not hasattr(node, 'col_offset'):
                node.col_offset = col_offset
            else:
                col_offset = node.col_offset
        for child in iter_child_nodes(node):
            _fix(child, lineno, col_offset)
    _fix(node, 1, 0)
    return node


def iter_child_nodes(node):
    """
    Yield all direct child nodes of *node*, that is, all fields that are nodes
    and all items of fields that are lists of nodes.
    """
    for name, field in iter_fields(node):
        if isinstance(field, (AST, _ast.AST)):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, (AST, _ast.AST)):
                    yield item


def iter_fields(node):
    """
    Yield a tuple of ``(fieldname, value)`` for each field in ``node._fields``
    that is present on *node*.
    """

    for field in node._fields or ():
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass


def walk(node):
    """
    Recursively yield all child nodes of *node*, in no specified order.  This is
    useful if you only want to modify nodes in place and don't care about the
    context.
    """
    from collections import deque
    todo = deque([node])
    while todo:
        node = todo.popleft()
        todo.extend(iter_child_nodes(node))
        yield node


class NodeVisitor(object):
    """
    A node visitor base class that walks the abstract syntax tree and calls a
    visitor function for every node found.  This function may return a value
    which is forwarded by the `visit` method.

    This class is meant to be subclassed, with the subclass adding visitor
    methods.

    Per default the visitor functions for the nodes are ``'visit_'`` +
    class name of the node.  So a `TryFinally` node visit function would
    be `visit_TryFinally`.  This behavior can be changed by overriding
    the `visit` method.  If no visitor function exists for a node
    (return value `None`) the `generic_visit` visitor is used instead.

    Don't use the `NodeVisitor` if you want to apply changes to nodes during
    traversing.  For this a special visitor exists (`NodeTransformer`) that
    allows modifications.
    """

    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        for field, value in iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, (AST, _ast.AST)):
                        self.visit(item)
            elif isinstance(value, (AST, _ast.AST)):
                self.visit(value)


class AST(object):
    _fields = ()
    _attributes = 'lineno', 'col_offset'

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        self._fields = self._fields or ()
        for name, value in zip(self._fields, args):
            setattr(self, name, value)


for name, cls in _ast.__dict__.items():
    if isinstance(cls, type) and issubclass(cls, _ast.AST):
        try:
            cls.__bases__ = (AST, ) + cls.__bases__
        except TypeError:
            pass


class ExceptHandler(AST):
    _fields = "type", "name", "body"
