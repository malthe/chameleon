Library Documentation
=====================

Chameleon Page Templates (CPT) is a system which can generate HTML and
XML.

The system is formed by the *Template Attribute Language* (*TAL*), the
*Expression Syntax* (*TALES*), *Intertionalization* (*I18N*) and the
*Macro Expansion Template Attribute Language* (*METAL*).

Note that this template system is based on (and closely resembles)
*Zope Page Templates* (ZPT). If you know that system, you should be
able to pick up the present system right away.

.. _getting-started-with-cpt:

Getting started
---------------

There are several template constructor classes available, one for each
of the combinations *text* or *xml*, and *string* or *file*.

Most projects will benefit from the simplicity of the template loader
utility::

  from chameleon import PageTemplateLoader
  templates = PageTemplateLoader("/some/absolute/path")

To load a template file ``"hello.pt"`` relative to the provided path,
use the dictionary syntax::

  template = templates['hello.pt']

The alternative is to invoke the appropriate constructor
directly. Let's try with a string input::

  from chameleon import PageTemplate
  template = PageTemplate("<div>Hello, $name.</div>")

All template instances are callable. Provide arguments as keywords::

  >>> template(name='John')
  '<div>Hello, John.</div>'

.. _fast:

Architecture
------------

The Chameleon template engine works as a compiler, turning page template markup
into a Python script. This technique significantly reduces processing
overhead and yields an improvement in render performance by a factor
of 5 to 10.

In real world applications such as `Plone <http://www.plone.org>`_,
this translates to an overall performance increase of 30-60%.

Compatibility
-------------

Chameleon runs on all Python platforms from 2.5 and up (including
Python 3.1+ and `pypy <http://pypy.org>`_).


Writing an expression compiler
------------------------------

To extend the language with a new expression prefix, you need to write
an expression compiler.

Let's try and write a compiler for an expression type that will simply
uppercase the supplied value.

.. code-block:: python

   import ast

   class UppercaseExpr(object):
       def __init__(self, string):
           self.string = string

       def __call__(self, target, engine):
           uppercased = self.string.uppercase()
           value = ast.Str(uppercased)
           return [ast.Assign(targets=[target], value=value)]

That's it for the compiler.

To make it available under a certain prefix, we'll add it to the
expression types dictionary.

.. code-block:: python

   from chameleon import PageTemplate

   PageTemplate.expression_type['upper'] = UppercaseExpr

To avoid changing the existing template class, instead we could have
subclassed, copied the existing ``expression_type`` dictionary and
added our expression compiler there.

Adding custom expressions can be a powerful way to make the templates
in your project more expressive.


Incompatibilities and differences
---------------------------------

There are a number of incompatibilities and differences between CPT
and ZPT. We list them here for a brief overview:

    *Default expression*

       The default expression is Python (or ``"python:"``). The *path*
       expression syntax is not supported in the base package.

    *Template arguments*

      Arguments passed by keyword to the render- or call method are
      inserted directly into the template execution namespace. This is
      different from ZPT where these are only available through the
      ``options`` dictionary.

      Zope::

        <div tal:content="options/title" />

      Chameleon::

        <div tal:content="title" />

    *Special symbols*

      The ``CONTEXTS`` symbol is not available.

The `z3c.pt <http://pypi.python.org/pypi/z3c.pt>`_ package works as a
compatibility layer. The template classes in this package provide a
implementation which is fully compatible with ZPT.


.. _new-features:

Language extensions
-------------------

The Chameleon page templates language comes with a number of features
and extensions. Some take inspiration from `Genshi
<http://genshi.edgewall.org/>`_.

    *Imports*

       The package introduces the ``import:`` expression which imports
       global names::

         <div tal:define="compile import: re.compile">
           ...

    *Tuple unpacking*

       The ``tal:define`` and ``tal:repeat`` clauses supports tuple
       unpacking::

          tal:define="(a, b, c) [1, 2, 3]"

       Extended `iterable unpacking
       <http://www.python.org/dev/peps/pep-3132/>`_ using the asterisk
       character is not currently supported (even for versions of
       Python that support it natively).

    *Dictionary lookup as fallback after attribute error*

       If attribute lookup (using the ``obj.<name>`` syntax) raises an
       ``AttributeError`` exception, a secondary lookup is attempted
       using dictionary lookup --- ``obj['<name>']``.

       Behind the scenes, this is done by rewriting all
       attribute-lookups to a custom lookup call:

       .. code-block:: python

            def lookup_attr(obj, key):
                try:
                    return getattr(obj, key)
                except AttributeError as exc:
                    try:
                        get = obj.__getitem__
                    except AttributeError:
                        raise exc
                    try:
                        return get(key)
                    except KeyError:
                        raise exc

    *Inline string substitution*

       In element attributes and in the text or tail of an element,
       string expression interpolation is available using the
       ``${...}`` syntax::

          <span class="content-${item_type}">
             ${title or item_id}
          </span>

    *Literal content*

       While the ``tal:content`` and ``tal:repeat`` attributes both
       support the ``structure`` keyword which inserts the content as
       a literal (without XML-escape), an object may also provide an
       ``__html__`` method to the same effect.

       The result of the method will be inserted as *structure*.

       This is particularly useful for content which is substituted
       using the expression operator: ``"${...}"`` since the
       ``structure`` keyword is not allowed here.

    *Switches*

       Two new attributes have been added: ``tal:switch`` and
       ``tal:case``. A case attribute works like a condition and only
       allows content if the value matches that of the nearest parent
       switch value.

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

1) Support for the ``tal:on-error`` from the reference specification
has been added.

2) Two new attributes ``tal:switch`` and ``tal:case`` have been added to make element conditions more flexible.

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

This section contains an autogenerated API reference.

The ``PageTemplate*`` constructors create template instances from
source files.

.. automodule:: chameleon

  .. autoclass:: chameleon.PageTemplate

  .. autoclass:: chameleon.PageTemplateFile

  .. autoclass:: chameleon.PageTextTemplate

  .. autoclass:: chameleon.PageTextTemplateFile

Some systems have framework support for loading templates from
files. The following loader class is directly compatible with the
Pylons framework and may be adapted to other frameworks:

.. class:: chameleon.PageTemplateLoader(search_path=None, **kwargs)

   .. automethod:: load

For advanced integration, the compiler module provides support for
dynamic expression evaluation:

.. automodule:: chameleon.compiler

  .. autoclass:: chameleon.compiler.ExpressionEvaluator
