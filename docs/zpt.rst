Zope Page Templates
===================

Zope Page Templates (ZPT) is a system which can generate HTML and XML.

ZPT is formed by the *Template Attribute Language* (*TAL*), the
*Expression Syntax* (*TALES*), *Intertionalization* (*I18N*) and the
*Macro Expansion Template Attribute Language* (*METAL*).

.. _getting-started-with-zpt:

Getting Started
---------------

There are several template constructor classes available, one for each
of the combinations *text* or *xml*, and *string* or *file*.

Most projects will benefit from the simplicity of the template loader
utility::

  from chameleon.zpt.loader import TemplateLoader
  templates = TemplateLoader("/some/absolute/path")

To load a template file ``"hello.pt"`` relative to the provided path,
use the dictionary syntax::

  template = templates['hello.pt']

The alternative is to invoke the appropriate constructor
directly. Let's try with a string input::

  from chameleon.zpt.template import PageTemplate
  template = PageTemplate("<div>Hello, $name.</div>")

All template instances are callable. Provide arguments as keywords::

  >>> template(name='John')
  '<div>Hello, John.</div>'

Learning the language
---------------------

For an introduction to the language, please see the `getting started
<http://www.zope.org/Documentation/Articles/ZPT1>`_ section on the
Zope website. Note that the expression language used in the examples
there is *path*, not Python.

Incompatibilities and Differences
---------------------------------

There are a number of incompatibilities and differences between the
Chameleon engine and the Zope reference implementation ---
`zope.pagetemplate
<http://pypi.python.org/pypi/zope.pagetemplate>`_. We list them below
for a brief overview. The reference implementation will be referred to
as *reference*:

    *Default expression*

       The default expression is Python (or ``"python:"``). The *path*
       expression syntax is not supported in the base package.

    *Template arguments*

      Arguments passed by keyword to the render- or call method are
      inserted directly into the template execution namespace. This is
      different from the reference implementation where these are only
      available through the ``options`` dictionary.

      Reference::

        <div tal:content="options/title" />

      Chameleon::

        <div tal:content="title" />

    *Special symbols*

      The ``CONTEXTS`` symbol is not available.

Language changes
----------------

The dialect implemented in Chameleon includes a number of new features
and extensions, some of which take inspiration from `Genshi
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
       character is not currently supported (even for platforms that
       support it natively).

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

    *Inline expression operator*

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

   from chameleon.zpt.template import PageTemplate

   PageTemplate.expression_type['upper'] = UppercaseExpr

To avoid changing the existing template class, instead we could have
subclassed, copied the existing ``expression_type`` dictionary and
added our expression compiler there.

Adding custom expressions can be a powerful way to make the templates
in your project more expressive.

Reference
---------

This reference is split into parts that correspond to each of the main
language features.

.. toctree::
   :maxdepth: 2

   tal
   tales
   metal
   i18n


API reference
-------------

This section contains an autogenerated API reference.

The ``PageTemplate*`` constructors create templates from XML files.

.. automodule:: chameleon.zpt.template

  .. autoclass:: chameleon.zpt.template.PageTemplate

  .. autoclass:: chameleon.zpt.template.PageTemplateFile

  .. autoclass:: chameleon.zpt.template.PageTextTemplate

  .. autoclass:: chameleon.zpt.template.PageTextTemplateFile

A template loader class is provided (for use with Pylons and other
platforms).

.. automodule:: chameleon.zpt.loader

  .. autoclass:: chameleon.zpt.loader.TemplateLoader
