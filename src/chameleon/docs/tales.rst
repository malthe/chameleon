.. _tales_chapter:

Template Attribute Language Expression Syntax (TALES)
=====================================================

The *Template Attribute Language Expression Syntax* (TALES) standard
describes expressions that supply :ref:`tal_chapter` and
:ref:`metal_chapter` with data.  TALES is *one* possible expression
syntax for these languages, but they are not bound to this definition.
Similarly, TALES could be used in a context having nothing to do with
TAL or METAL.

TALES expressions are described below with any delimiter or quote
markup from higher language layers removed.  Here is the basic
definition of TALES syntax::

      Expression  ::= [type_prefix ':'] String
      type_prefix ::= Name

Here are some simple examples::

      1 + 2
      None
      string:Hello, ${view.user_name}

The optional *type prefix* determines the semantics and syntax of the
*expression string* that follows it.  A given implementation of TALES
can define any number of expression types, with whatever syntax you
like. It also determines which expression type is indicated by
omitting the prefix.

TALES Expression Types
----------------------

These are the TALES expression types supported by default in
:mod:`chameleon.zpt`:

* ``python`` - execute a Python expression

* ``string`` - format a string

.. note:: if you do not specify a prefix within an expression context,
   :mod:`chameleon.zpt`` assumes that the expression is a *python*
   expression.

There's a mechanism to allow fallback to alternative expressions, if one should fail (raise an exception). The pipe character ('|') is used to separate two expressions.

.. warning:: The reference implementation of ZPT has a number of expression types that are closely tied to the Zope framework.

.. _tales_built_in_names:

Built-in Names
--------------

These are the names always available to TALES expressions in
:mod:`chameleon.zpt`:

- ``default`` - special value used to specify that existing text or attributes should not be replaced. See the documentation for individual TAL statements for details on how they interpret *default*.

- ``repeat`` - the *repeat* variables; see :ref:`tal_repeat` for more
  information.

- ``template`` - reference to the template which was first called; this symbol is carried over when using macros.

- ``macros`` - reference to the macros dictionary that corresponds to the current template.
  
``python`` expressions
----------------------

Syntax
~~~~~~

Python expression syntax::

        Any valid Python language expression

Description
~~~~~~~~~~~

Python expressions are executed natively within the translated template source code. There is no built-in security apparatus.

``string`` expressions
----------------------

Syntax
~~~~~~

String expression syntax::

        string_expression ::= ( plain_string | [ varsub ] )*
        varsub            ::= ( '$' Variable ) | ( '${ Expression }' )
        plain_string      ::= ( '$$' | non_dollar )*
        non_dollar        ::= any character except '$'

Description
~~~~~~~~~~~

String expressions interpret the expression string as text. If no
expression string is supplied the resulting string is *empty*. The
string can contain variable substitutions of the form ``$name`` or
``${expression}``, where ``name`` is a variable name, and ``expression`` is a TALES-expression. The escaped string value of the expression is inserted into the string.

.. note:: To prevent a ``$`` from being interpreted this
   way, it must be escaped as ``$$``.

Examples
~~~~~~~~

Basic string formatting::

    <span tal:replace="string:$this and $that">
      Spam and Eggs
    </span>

    <p tal:content="string:${request.form['total']}">
      total: 12
    </p>

Including a dollar sign::

    <p tal:content="string:$$$cost">
      cost: $42.00
    </p>

