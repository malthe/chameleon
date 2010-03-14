.. _metal_chapter:

Macro Expansion Template Attribute Language (METAL)
===================================================

The *Macro Expansion Template Attribute Language* (METAL) standard is
a facility for HTML/XML macro preprocessing. It can be used in
conjunction with or independently of TAL and TALES.

Macros provide a way to define a chunk of presentation in one
template, and share it in others, so that changes to the macro are
immediately reflected in all of the places that share it.
Additionally, macros are always fully expanded, even in a template's
source text, so that the template appears very similar to its final
rendering.

A single Page Template can accomodate multiple macros.

METAL Namespace
---------------

The METAL namespace URI and recommended alias are currently defined
as::

        xmlns:metal="http://xml.zope.org/namespaces/metal"

Just like the TAL namespace URI, this URI is not attached to a web
page; it's just a unique identifier.  This identifier must be used in
all templates which use METAL.

METAL Statements
----------------

METAL defines a number of statements:

* ``metal:define-macro`` Define a macro.
* ``metal:use-macro`` Use a macro.
* ``metal:define-slot`` Define a macro customization point.
* ``metal:fill-slot`` Customize a macro.

Although METAL does not define the syntax of expression non-terminals,
leaving that up to the implementation, a canonical expression syntax
for use in METAL arguments is described in TALES Specification.

``define-macro``: Define a macro
--------------------------------

Syntax
~~~~~~

``metal:define-macro`` syntax::

        argument ::= Name

Description
~~~~~~~~~~~

The ``metal:define-macro`` statement defines a macro. The macro is named
by the statement expression, and is defined as the element and its
sub-tree.

Examples
~~~~~~~~

Simple macro definition::

        <p metal:define-macro="copyright">
          Copyright 2004, <em>Foobar</em> Inc.
        </p>

``define-slot``: Define a macro customization point
---------------------------------------------------

Syntax
~~~~~~

``metal:define-slot`` syntax::

        argument ::= Name

Description
~~~~~~~~~~~

The ``metal:define-slot`` statement defines a macro customization
point or *slot*. When a macro is used, its slots can be replaced, in
order to customize the macro. Slot definitions provide default content
for the slot. You will get the default slot contents if you decide not
to customize the macro when using it.

The ``metal:define-slot`` statement must be used inside a
``metal:define-macro`` statement.

Slot names must be unique within a macro.

Examples
~~~~~~~~

Simple macro with slot::

        <p metal:define-macro="hello">
          Hello <b metal:define-slot="name">World</b>
        </p>

This example defines a macro with one slot named ``name``. When you use
this macro you can customize the ``b`` element by filling the ``name``
slot.

``fill-slot``: Customize a macro
--------------------------------

Syntax
~~~~~~

``metal:fill-slot`` syntax::

        argument ::= Name

Description
~~~~~~~~~~~

The ``metal:fill-slot`` statement customizes a macro by replacing a
*slot* in the macro with the statement element (and its content).

The ``metal:fill-slot`` statement must be used inside a
``metal:use-macro`` statement.

Slot names must be unique within a macro.

If the named slot does not exist within the macro, the slot
contents will be silently dropped.

Examples
~~~~~~~~

Given this macro::

        <p metal:define-macro="hello">
          Hello <b metal:define-slot="name">World</b>
        </p>

You can fill the ``name`` slot like so::

        <p metal:use-macro="container/master.html/macros/hello">
          Hello <b metal:fill-slot="name">Kevin Bacon</b>
        </p>

``use-macro``: Use a macro
--------------------------

Syntax
~~~~~~

``metal:use-macro`` syntax::

        argument ::= expression

Description
~~~~~~~~~~~

The ``metal:use-macro`` statement replaces the statement element with
a macro. The statement expression describes a macro definition.

.. note:: In Chameleon the expression may point to a template instance; in this case it will be rendered in its entirety.

In :mod:`zc.pt` the expression will generally be a expression
referring to a macro defined in another template which is passed in to
the rendering template. See ``metal:define-macro`` for more
information.

The effect of expanding a macro is to graft a subtree from another
document (or from elsewhere in the current document) in place of the
statement element, replacing the existing sub-tree.  Parts of the
original subtree may remain, grafted onto the new subtree, if the
macro has *slots*. See ``metal:define-slot`` for more information. If
the macro body uses any macros, they are expanded first.

When a macro is expanded, its ``metal:define-macro`` attribute is
replaced with the ``metal:use-macro`` attribute from the statement
element.  This makes the root of the expanded macro a valid
``use-macro`` statement element.

Examples
~~~~~~~~

Basic macro usage::

        <p metal:use-macro="other/macros/header"> header macro from
          defined in other.html template </p>

This example refers to the ``header`` macro defined in the ``other``
template which has been passed as a keyword argument to ``zc.pt``'s
``render`` method. When the macro is expanded, the ``p`` element and
its contents will be replaced by the macro.

.. note:: there will still be a ``metal:use-macro`` attribute on the
   replacement element.

