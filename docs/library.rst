Library Documentation
=====================

This section documents the package as a Python library. To learn about
the page template language, consult the :ref:`language reference
<language-reference>`.

.. _getting-started-with-cpt:

Getting started
---------------

There are several template constructor classes available, one for each
of the combinations *text* or *xml*, and *string* or *file*.

The file-based constructor requires an absolute path. To set up a
templates directory *once*, use the template loader class::

  import os

  path = os.path.dirname(__file__)

  from chameleon import PageTemplateLoader
  templates = PageTemplateLoader(os.path.join(path, "templates"))

Then, to load a template relative to the provided path, use dictionary
syntax::

  template = templates['hello.pt']

Alternatively, use the appropriate template class directly. Let's try
with a string input::

  from chameleon import PageTemplate
  template = PageTemplate("<div>Hello, ${name}.</div>")

All template instances are callable. Provide variables by keyword
argument::

  >>> template(name='John')
  '<div>Hello, John.</div>'

.. _fast:

Performance
-----------

The template engine compiles (or *translates*) template source code
into Python byte-code. In simple templates this yields an increase in
performance of about 7 times in comparison to the reference
implementation.

In benchmarks for the content management system `Plone
<http://www.plone.org>`_, switching to Chameleon yields a request to
response improvement of 20-50%.

Extension
---------

You can extend the language through the expression engine by writing
your own expression compiler.

Let's try and write an expression compiler for an expression type that
will simply uppercase the supplied value. We'll call it ``upper``.

You can write such a compiler as a closure:

.. code-block:: python

   import ast

   def uppercase_expression(string):
       def compiler(target, engine):
           uppercased = self.string.uppercase()
           value = ast.Str(uppercased)
           return [ast.Assign(targets=[target], value=value)]
       return compiler

To make it available under a certain prefix, we'll add it to the
expression types dictionary.

.. code-block:: python

   from chameleon import PageTemplate
   PageTemplate.expression_types['upper'] = uppercase_expression

Alternatively, you could subclass the template class and set the
attribute ``expression_types`` to a dictionary that includes your
expression:

.. code-block:: python

   from chameleon import PageTemplateFile
   from chameleon.tales import PythonExpr

   class MyPageTemplateFile(PageTemplateFile):
       expression_types = {
           'python': PythonExpr,
           'upper': uppercase_expression
           }

You can now uppercase strings *natively* in your templates::

  <div tal:content="upper: hello, world" />

It's probably best to stick with a Python expression::

  <div tal:content="'hello, world'.upper()" />


.. _whats-new:

Changes between 1.x and 2.x
---------------------------

This sections describes new features, improvements and changes from
1.x to 2.x.

New parser
~~~~~~~~~~

This series features a new, custom-built parser, implemented in pure
Python. It parses both HTML and XML inputs (the previous parser relied
on the expat system library and was more strict about its input).

The main benefit of the new parser is that the compiler is now able to
point to the source location of parse- and compilation errors much
more accurately. This should be a great aid in debugging these errors.

Compatible output
~~~~~~~~~~~~~~~~~

The 2.x engine matches the output of the reference implementation more
closely (usually exactly). There are less differences altogether; for
instance, the method of escaping TALES expression (usually a
semicolon) has been changed to match that of the reference
implementation.

New language features
~~~~~~~~~~~~~~~~~~~~~

This series also introduces a number of new language features:

1. Support for the ``tal:on-error`` from the reference specification
   has been added.

2. Two new attributes ``tal:switch`` and ``tal:case`` have been added
   to make element conditions more flexible.


Code improvements
~~~~~~~~~~~~~~~~~

The template classes have been refactored and simplified allowing
better reuse of code and more intuitive APIs on the lower levels.

Expression engine
~~~~~~~~~~~~~~~~~

The expression engine has been redesigned to make it easier to
understand and extend. The new engine is based on the ``ast`` module
(available since Python 2.6; backports included for Python 2.5). This
means that expression compilers now need to return a valid list of AST
statements that include an assignment to the target node.

Compiler
~~~~~~~~

The new compiler has been optimized for complex templates. As a
result, in the benchmark suite included with the package, this
compiler scores about half of the 1.x series. For most real world
applications, the engine should still perform as well as the 1.x
series.


API reference
-------------

This section describes the documented API of the library.

Template classes
~~~~~~~~~~~~~~~~

Use the ``PageTemplate*`` template classes to define a template from a
string or file input:

.. automodule:: chameleon

  .. autoclass:: chameleon.PageTemplate

     Note: The remaining classes take the same general configuration
     arguments.

     .. automethod:: render

  .. autoclass:: chameleon.PageTemplateFile(filename, **config)

  .. autoclass:: chameleon.PageTextTemplate

  .. autoclass:: chameleon.PageTextTemplateFile

Template loader
~~~~~~~~~~~~~~~

Some systems have framework support for loading templates from
files. The following loader class is directly compatible with the
Pylons framework and may be adapted to other frameworks:

.. class:: chameleon.PageTemplateLoader(search_path=None, default_extension=None, **config)

   Load templates from ``search_path`` (must be a string or a list of
   strings)::

     templates = PageTemplateLoader(path)
     example = templates['example.pt']

   If ``default_extension`` is provided, this will be added to inputs
   that do not already have an extension::

     templates = PageTemplateLoader(path, ".pt")
     example = templates['example']

   Any additional keyword arguments will be passed to the template
   constructor::

     templates = PageTemplateLoader(path, debug=True, encoding="utf-8")

   .. automethod:: load

Expression engine
~~~~~~~~~~~~~~~~~

For advanced integration, the compiler module provides support for
dynamic expression evaluation:

.. automodule:: chameleon.compiler

  .. autoclass:: chameleon.compiler.ExpressionEvaluator
