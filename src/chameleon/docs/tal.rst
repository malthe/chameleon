.. _tal_chapter:

Template Attribute Language (TAL)
=================================

The *Template Attribute Language* (TAL) is an attribute language used
to create dynamic XML-like content.  It allows elements of a document
to be replaced, repeated, or omitted.

An attribute language is a programming language designed to render
documents written in XML markup.  The input XML must be well-formed.
The output from the template is usually XML-like but isn't required to
be well-formed.

The statements of the language are document tags with special
attributes, and look like this::

    <p namespace:command="argument">Some Text</p>

In the above example, the attribute ``namespace:command="argument"``
is the statement, and the entire paragraph tag is the statement's
element.  The statement's element is the portion of the document on
which this statement operates.

Each statement has three parts: the namespace prefix, the name, and
the argument.  The prefix identifies the language, and must be
introduced by an XML namespace declaration in XML and XHTML documents,
like this::

    xmlns:namespace="http://example.com/namespace"

The statements of TAL are XML attributes from the TAL namespace.
These attributes can be applied to an XML or HTML document in order to
make it act as a template.

The TAL namespace URI is currently defined as::

   xmlns:tal="http://xml.zope.org/namespaces/tal"

This is not a URL, but merely a unique identifier.  Do not expect a
browser to resolve it successfully.  This definition is required in
every file that uses ZPT.  For example::

  <div xmlns="http://www.w3.org/1999/xhtml"
       xmlns:tal="http://xml.zope.org/namespaces/tal">
       .... rest of the template here ...
  </div>

All templates that you use ZPT in *must* include the
``xmlns:tal="http://xml.zope.org/namespaces/tal"`` attribute on some
top-level tag.

TAL Statements
--------------

A **TAL statement** has a name (the attribute name) and an argument
(the attribute value).  For example, a ``tal:content`` statement might
look like ``tal:content="string:Hello"``.  The element on which a
statement is defined is its **statement element**.  Most TAL
statements are *expressions*, but the syntax and semantics of these
expressions are not part of TAL.

.. note:: *TALES* is used as the expression language for the "stuff in
   the quotes" typically.  TALES is documented separately.

These are the available TAL statements:

- ``tal:attributes`` - dynamically change element attributes.

- ``tal:define`` - define variables.

- ``tal:condition`` - test conditions.

- ``tal:content`` - replace the content of an element.

- ``tal:omit-tag`` - remove an element, leaving the content of the
  element.

- ``tal:repeat`` - repeat an element.

- ``tal:replace`` - replace the content of an element and remove the
  element leaving the content.

- ``tal:default-expression`` - set the default expression type for a
  block of tags.

.. warning:: The reference implementation of ZPT has an additonal command
   ``tal:on-error`` which :mod:`chameleon.zpt` does not implement.

Order of Operations
-------------------

When there is only one TAL statement per element, the order in which
they are executed is simple.  Starting with the root element, each
element's statements are executed, then each of its child elements is
visited, in order, to do the same.

Any combination of statements may appear on the same element, except
that the ``tal:content`` and ``tal:replace`` statements may not be
used on the same element.

TAL does not use use the order in which statements are written in the
tag to determine the order in which they are executed.  When an
element has multiple statements, they are executed in this order:

#. ``tal:define``

#. ``tal:condition``

#. ``tal:repeat``

#. ``tal:content`` or ``tal:replace``

#. ``tal:omit-tag``

#. ``tal:attributes``

There is a reasoning behind this ordering.  Because users often want
to set up variables for use in other statements contained within this
element or subelements, ``tal:define`` is executed first.
``tal:condition`` follows, then ``tal:repeat`` , then ``tal:content``
or ``tal:replace``. Finally, before ``tal:attributes``, we have
``tal:omit-tag`` (which is implied with ``tal:replace``).

``tal:attributes``: Replace element attributes
----------------------------------------------

Syntax
~~~~~~

``tal:attributes`` syntax::

    argument             ::= attribute_statement [';' attribute_statement]*
    attribute_statement  ::= attribute_name expression
    attribute_name       ::= [namespace-prefix ':'] Name
    namespace-prefix     ::= Name

.. warning:: The reference implementation of ZPT requires you to escape the semi-colon (;) literal by doubling it (``;;``). With :mod:`chameleon.zpt` this is only required when using the ``string`` expression and when defining variables (it will result in the literal being printed twice in all other situations).

Description
~~~~~~~~~~~

The ``tal:attributes`` statement replaces the value of an attribute
(or creates an attribute) with a dynamic value.  The
value of each expression is converted to a string, if necessary.

.. note:: You can qualify an attribute name with a namespace prefix,
   for example ``html:table``, if you are generating an XML document
   with multiple namespaces.

If an attribute expression evaluates to ``None``, then that attribute is deleted from the statement element.

.. warning:: The ``nothing`` symbol is not defined in :mod:`chameleon.zpt`. The standard Python null-value ``None`` is be used in its place.

If the expression evaluates to the symbol ``default`` (a symbol which is always available when evaluating attributes), its value is defined as the default static attribute value.

If you use ``tal:attributes`` on an element with an active
``tal:replace`` command, the ``tal:attributes`` statement is ignored.

If you use ``tal:attributes`` on an element with a ``tal:repeat``
statement, the replacement is made on each repetition of the element,
and the replacement expression is evaluated fresh for each repetition.

Examples
~~~~~~~~

Replacing a link::

    <a href="/sample/link.html"
     tal:attributes="href context.url()">

Replacing two attributes::

    <textarea rows="80" cols="20"
     tal:attributes="rows request.rows();cols request.cols()">

``tal:condition``: Conditionally insert or remove an element
------------------------------------------------------------

Syntax
~~~~~~

``tal:condition`` syntax::

    argument ::= expression

Description
~~~~~~~~~~~

 The ``tal:condition`` statement includes the statement element in the
 template only if the condition is met, and omits it otherwise.  If
 its expression evaluates to a *true* value, then normal processing of
 the element continues, otherwise the statement element is immediately
 removed from the template.  For these purposes, the value ``nothing``
 is false, and ``default`` has the same effect as returning a true
 value.

.. note:: Like Python itself, ZPT considers None, zero, empty strings,
   empty sequences, empty dictionaries, and instances which return a
   nonzero value from ``__len__`` or ``__nonzero__`` false; all other
   values are true, including ``default``.

Examples
~~~~~~~~

Test a variable before inserting it::

        <p tal:condition="request.message"
           tal:content="request.message">
           message goes here
        </p>

Testing for odd/even in a repeat-loop::

        <div tal:repeat="item range(10)">
          <p tal:condition="repeat.item.even">Even</p>
          <p tal:condition="repeat.item.odd">Odd</p>
        </div>

``tal:content``: Replace the content of an element
--------------------------------------------------
 
Syntax
~~~~~~

``tal:content`` syntax::

        argument ::= (['text'] | 'structure') expression

Description
~~~~~~~~~~~

Rather than replacing an entire element, you can insert text or
structure in place of its children with the ``tal:content`` statement.
The statement argument is exactly like that of ``tal:replace``, and is
interpreted in the same fashion.  If the expression evaluates to
``nothing``, the statement element is left childless.  If the
expression evaluates to ``default``, then the element's contents are
unchanged.

The default replacement behavior is ``text``, which replaces
angle-brackets and ampersands with their HTML entity equivalents.  The
``structure`` keyword passes the replacement text through unchanged,
allowing HTML/XML markup to be inserted.  This can break your page if
the text contains unanticipated markup (eg.  text submitted via a web
form), which is the reason that it is not the default.

Examples
~~~~~~~~

Inserting the user name::

        <p tal:content="user.getUserName()">Fred Farkas</p>

Inserting HTML/XML::

        <p tal:content="structure context.getStory()">marked <b>up</b>
        content goes here.</p>

``tal:define``: Define variables
--------------------------------

Syntax
~~~~~~

``tal:define`` syntax::

    argument             ::= attribute_statement [';' attribute_statement]*
    attribute_statement  ::= variable_name expression
    variable_name        ::= Name

.. warning:: The reference implementation of ZPT requires you to escape the semi-colon (;) literal by doubling it (``;;``). With :mod:`chameleon.zpt` this is only required when using the ``string`` expression and when defining variables (it will result in the literal being printed twice in all other situations).

Description
~~~~~~~~~~~

The ``tal:define`` statement defines variables.  When you define a
local variable in a statement element, you can use that variable in
that element and the elements it contains.  If you redefine a variable
in a contained element, the new definition hides the outer element's
definition within the inner element.  

If the expression associated with a variable evaluates to ``nothing``,
then that variable has the value ``nothing``, and may be used as such
in further expressions. Likewise, if the expression evaluates to
``default``, then the variable has the value ``default``, and may be
used as such in further expressions.

Examples
~~~~~~~~

Defining a variable::

        tal:define="company_name 'Zope Corp, Inc.'"

Defining two variables, where the second depends on the first::

        tal:define="mytitle context.title; tlen len(mytitle)"

``tal:omit-tag``: Remove an element, leaving its contents
---------------------------------------------------------

Syntax
~~~~~~

``tal:omit-tag`` syntax::

        argument ::= [ expression ]

Description
~~~~~~~~~~~

The ``tal:omit-tag`` statement leaves the contents of an element in
place while omitting the surrounding start and end tags.

If the expression evaluates to a *false* value, then normal processing
of the element continues and the tags are not omitted.  If the
expression evaluates to a *true* value, or no expression is provided,
the statement element is replaced with its contents.

.. note:: Like Python itself, ZPT considers None, zero, empty strings,
   empty sequences, empty dictionaries, and instances which return a
   nonzero value from ``__len__`` or ``__nonzero__`` false; all other
   values are true, including ``default``.

Examples
~~~~~~~~

Unconditionally omitting a tag::

        <div tal:omit-tag="" comment="This tag will be removed">
          <i>...but this text will remain.</i>
        </div>

Conditionally omitting a tag::

        <b tal:omit-tag="not:bold">I may be bold.</b>

The above example will omit the ``b`` tag if the variable ``bold`` is false.

Creating ten paragraph tags, with no enclosing tag::

        <span tal:repeat="n range(10)"
              tal:omit-tag="">
          <p tal:content="n">1</p>
        </span>

.. _tal_repeat:

``tal:repeat``: Repeat an element
---------------------------------

Syntax
~~~~~~

``tal:repeat`` syntax::

        argument      ::= variable_name expression
        variable_name ::= Name

Description
~~~~~~~~~~~

The ``tal:repeat`` statement replicates a sub-tree of your document
once for each item in a sequence. The expression should evaluate to a
sequence. If the sequence is empty, then the statement element is
deleted, otherwise it is repeated for each value in the sequence.  If
the expression is ``default``, then the element is left unchanged, and
no new variables are defined.

The ``variable_name`` is used to define a local variable and a repeat
variable. For each repetition, the local variable is set to the
current sequence element, and the repeat variable is set to an
iteration object.

Repeat Variables
~~~~~~~~~~~~~~~~~

You use repeat variables to access information about the current
repetition (such as the repeat index).  The repeat variable has the
same name as the local variable, but is only accessible through the
built-in variable named ``repeat``.

The following information is available from the repeat variable:

- ``index`` - repetition number, starting from zero.

- ``number`` - repetition number, starting from one.

- ``even`` - true for even-indexed repetitions (0, 2, 4, ...).

- ``odd`` - true for odd-indexed repetitions (1, 3, 5, ...).

- ``start`` - true for the starting repetition (index 0).

- ``end`` - true for the ending, or final, repetition.

- ``first`` - true for the first item in a group - see note below

- ``last`` - true for the last item in a group - see note below

- ``length`` - length of the sequence, which will be the total number
  of repetitions.

- ``letter`` - repetition number as a lower-case letter: "a" - "z",
  "aa" - "az", "ba" - "bz", ..., "za" - "zz", "aaa" - "aaz", and so
  forth.

- ``Letter`` - upper-case version of *letter*.

- ``roman`` - repetition number as a lower-case roman numeral:
  "i", "ii", "iii", "iv", "v", etc.

- ``Roman`` - upper-case version of *roman*.

You can access the contents of the repeat variable using either dictionary- or attribute-style access, e.g. ``repeat['item'].start`` or ``repeat.item.start``.

.. note:: For legacy compatibility, the attributes ``odd``, ``even``, ``number``, ``letter``, ``Letter``, ``roman``, and ``Roman`` are callable (returning ``self``).

Note that ``first`` and ``last`` are intended for use with sorted
sequences.  They try to divide the sequence into group of items with
the same value.

Examples
~~~~~~~~

Iterating over a sequence of strings::    

        <p tal:repeat="txt ('one', 'two', 'three')">
           <span tal:replace="txt" />
        </p>

Inserting a sequence of table rows, and using the repeat variable
to number the rows::

        <table>
          <tr tal:repeat="item here.cart">
              <td tal:content="repeat.item.number">1</td>
              <td tal:content="item.description">Widget</td>
              <td tal:content="item.price">$1.50</td>
          </tr>
        </table>

Nested repeats::

        <table border="1">
          <tr tal:repeat="row range(10)">
            <td tal:repeat="column range(10)">
              <span tal:define="x repeat.row.number; 
                                y repeat.column.number; 
                                z x * y"
                    tal:replace="string:$x * $y = $z">1 * 1 = 1</span>
            </td>
          </tr>
        </table>

Insert objects. Separates groups of objects by type by drawing a rule
between them::

        <div tal:repeat="object objects">
          <h2 tal:condition="repeat.object.first.meta_type"
            tal:content="object.type">Meta Type</h2>
          <p tal:content="object.id">Object ID</p>
          <hr tal:condition="object.last.meta_type" />
        </div>

.. note:: the objects in the above example should already be sorted by
   type.

``tal:replace``: Replace an element
-----------------------------------

Syntax
~~~~~~

``tal:replace`` syntax::

        argument ::= ['structure'] expression

Description
~~~~~~~~~~~


The ``tal:replace`` statement replaces an element with dynamic
content.  It replaces the statement element with either text or a
structure (unescaped markup). The body of the statement is an
expression with an optional type prefix. The value of the expression
is converted into an escaped string unless you provide the 'structure' prefix. Escaping consists of converting ``&amp;`` to
``&amp;amp;``, ``&lt;`` to ``&amp;lt;``, and ``&gt;`` to ``&amp;gt;``.

.. note:: If the inserted object provides an ``__html__`` method, that method is called with the result inserted as structure. This feature is not implemented by ZPT.

If the expression evaluates to ``None``, the element is simply removed.  If the value is ``default``, then the element is left unchanged.

Examples
~~~~~~~~

Inserting a title::

        <span tal:replace="context.title">Title</span>

Inserting HTML/XML::

        <div tal:replace="structure table" />

