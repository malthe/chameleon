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


API reference
-------------

This section describes the documented API of the library.


Templates
~~~~~~~~~

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

Loader
~~~~~~

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


Exceptions
~~~~~~~~~~

Chameleon may raise exceptions during both the cooking and the
rendering phase, but those raised during the cooking phase (parse and
compile) all inherit from a single base class:

.. class:: chameleon.TemplateError(msg, token)

   This exception is the base class of all exceptions raised by the
   template engine in the case where a template has an error.

   It may be raised during rendering since templates are processed
   lazily (unless eager loading is enabled).


An error that occurs during the rendering of a template is wrapped in
an exception class to disambiguate the two cases:

.. class:: chameleon.RenderError(*args)

   Indicates an exception that resulted from the evaluation of an
   expression in a template.

   A complete traceback is attached to the exception beginning with
   the expression that resulted in the error. The traceback includes
   a string representation of the template variable scope for further
   reference.


Expressions
~~~~~~~~~~~

For advanced integration, the compiler module provides support for
dynamic expression evaluation:

.. automodule:: chameleon.compiler

  .. autoclass:: chameleon.compiler.ExpressionEvaluator
