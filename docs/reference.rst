:tocdepth: 4

.. _language-reference:

.. highlight:: xml

Language Reference
==================

The language reference is structured such that it can be read as a
general introduction to the *page templates* language.

It's split into parts that correspond to each of the main language
features.

Syntax
######

You can safely :ref:`skip this section <tal>` if you're familiar with
how template languages work or just want to learn by example.

An *attribute language* is a programming language designed to render
documents written in XML or HTML markup.  The input must be a
well-formed document.  The output from the template is usually
XML-like but isn't required to be well-formed.

The statements of the language are document tags with special
attributes, and look like this::

    <p namespace-prefix:command="argument"> ... </p>

In the above example, the attribute
``namespace-prefix:command="argument"`` is the statement, and the
entire paragraph tag is the statement's element.  The statement's
element is the portion of the document on which this statement
operates.

The namespace prefixes are typically declared once, at the top of a
template (note that prefix declarations for the template language
namespaces are omitted from the template output)::

  <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:tal="http://xml.zope.org/namespaces/tal"
        xmlns:metal="http://xml.zope.org/namespaces/metal"
        xmlns:i18n="http://xml.zope.org/namespaces/i18n">
    ...
  </html>

Thankfully, sane namespace prefix defaults are in place to let us skip
most of the boilerplate::

  <html xmlns="http://www.w3.org/1999/xhtml">
    <body>
      <p tal:content="text"> ... </p>
    </body>
  </html>

Note how ``tal`` is used without an explicit namespace
declaration. Chameleon sets up defaults for ``metal`` and ``i18n`` as
well.

.. note:: Default prefixes are a special feature of Chameleon.

.. _tal:

Basics (TAL)
############

The *template attribute language* is used to create dynamic XML-like
content.  It allows elements of a document to be replaced, repeated,
or omitted.

Statements
----------

These are the available statements:

==================  ==============
 Statement           Description
==================  ==============
``tal:define``      Define variables.
``tal:switch``      Defines a switch condition
``tal:condition``   Include element only if expression is true.
``tal:repeat``      Repeat an element.
``tal:case``        Includes element only if expression is equal to parent switch.
``tal:content``     Substitute the content of an element.
``tal:replace``     Replace the element with dynamic content.
``tal:omit-tag``    Omit the element tags, leaving only the inner content.
``tal:attributes``  Dynamically change or insert element attributes.
``tal:on-error``    Substitute the content of an element if processing fails.
==================  ==============

When there is only one TAL statement per element, the order in which
they are executed is simple.  Starting with the root element, each
element's statements are executed, then each of its child elements is
visited, in order, to do the same::

  <html>
    <meta>
      <title tal:content="context.title" />
    </meta>
    <body>
      <div tal:condition="items">
        <p>These are your items:</p>
        <ul>
          <li tal:repeat="item items" tal:content="item" />
        </ul>
      </div>
    </body>
  </html>

Any combination of statements may appear on the same element, except
that the ``tal:content`` and ``tal:replace`` statements may not be
used on the same element.

.. note:: The ``tal:case`` and ``tal:switch`` statements are available
          in Chameleon only.

TAL does not use use the order in which statements are written in the
tag to determine the order in which they are executed.  When an
element has multiple statements, they are executed in the order
printed in the table above.

There is a reasoning behind this ordering.  Because users often want
to set up variables for use in other statements contained within this
element or subelements, ``tal:define`` is executed first. Then any
switch statement. ``tal:condition`` follows, then ``tal:repeat``, then
``tal:case``. We are now rendering an element; first ``tal:content``
or ``tal:replace``. Finally, before ``tal:attributes``, we have
``tal:omit-tag`` (which is implied with ``tal:replace``).

.. note:: *TALES* is used as the expression language for the "stuff in
   the quotes". The default syntax is simply Python, but
   other inputs are possible --- see the section on :ref:`expressions
   <tales>`.

``tal:attributes``
^^^^^^^^^^^^^^^^^^

Updates or inserts element attributes.

::

  tal:attributes="href request.url"

Syntax
~~~~~~

``tal:attributes`` syntax::

    argument             ::= attribute_statement [';' attribute_statement]*
    attribute_statement  ::= attribute_name expression
    attribute_name       ::= [namespace-prefix ':'] Name
    namespace-prefix     ::= Name


Description
~~~~~~~~~~~

The ``tal:attributes`` statement replaces the value of an attribute
(or creates an attribute) with a dynamic value.  The
value of each expression is converted to a string, if necessary.

.. note:: You can qualify an attribute name with a namespace prefix,
   for example ``html:table``, if you are generating an XML document
   with multiple namespaces.

If an attribute expression evaluates to ``None``, the attribute is
deleted from the statement element (or simply not inserted).

If the expression evaluates to the symbol ``default`` (a symbol which
is always available when evaluating attributes), its value is defined
as the default static attribute value. If there is no such default
value, a return value of ``default`` will drop the attribute.

If you use ``tal:attributes`` on an element with an active
``tal:replace`` command, the ``tal:attributes`` statement is ignored.

If you use ``tal:attributes`` on an element with a ``tal:repeat``
statement, the replacement is made on each repetition of the element,
and the replacement expression is evaluated fresh for each repetition.

.. note:: If you want to include a semicolon (";") in an expression, it
          must be escaped by doubling it (";;") [1]_.

Examples
~~~~~~~~

Replacing a link::

    <a href="/sample/link.html"
       tal:attributes="href context.url()"
       >
       ...
    </a>

Replacing two attributes::

    <textarea rows="80" cols="20"
              tal:attributes="rows request.rows();cols request.cols()"
        />

A checkbox input::

    <input type="input" tal:attributes="checked True" />

``tal:condition``
^^^^^^^^^^^^^^^^^

Conditionally includes or omits an element::

  <div tal:condition="comments">
    ...
  </div>

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

        <p tal:condition="request.message" tal:content="request.message" />

Testing for odd/even in a repeat-loop::

        <div tal:repeat="item range(10)">
          <p tal:condition="repeat.item.even">Even</p>
          <p tal:condition="repeat.item.odd">Odd</p>
        </div>

``tal:content``
^^^^^^^^^^^^^^^

Replaces the content of an element.

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
evaluated.

The default replacement behavior is ``text``, which replaces
angle-brackets and ampersands with their HTML entity equivalents.  The
``structure`` keyword passes the replacement text through unchanged,
allowing HTML/XML markup to be inserted.  This can break your page if
the text contains unanticipated markup (eg.  text submitted via a web
form), which is the reason that it is not the default.

.. note:: The ``structure`` keyword exists to provide backwards
          compatibility.  In Chameleon, the ``structure:`` expression
          type provides the same functionality (also for inline
          expressions).


Examples
~~~~~~~~

Inserting the user name::

        <p tal:content="user.getUserName()">Fred Farkas</p>

Inserting HTML/XML::

        <p tal:content="structure context.getStory()">
           Marked <b>up</b> content goes here.
        </p>

``tal:define``
^^^^^^^^^^^^^^

Defines local variables.

Syntax
~~~~~~

``tal:define`` syntax::

    argument ::= define_scope [';' define_scope]*
    define_scope ::= (['local'] | 'global')
    define_var define_var ::= variable_name
    expression variable_name ::= Name

Description
~~~~~~~~~~~

The ``tal:define`` statement defines variables.  When you define a
local variable in a statement element, you can use that variable in
that element and the elements it contains.  If you redefine a variable
in a contained element, the new definition hides the outer element's
definition within the inner element.

Note that valid variable names are any Python identifier string
including underscore, although two or more leading underscores are
disallowed (used internally by the compiler). Further, names are
case-sensitive.

Python builtins are always "in scope", but most of them may be
redefined (such as ``help``). Exceptions are:: ``float``, ``int``,
``len``, ``long``, ``str``, ``None``, ``True`` and ``False``.

In addition, the following names are reserved: ``econtext``,
``rcontext``, ``translate``, ``decode`` and ``convert``.

If the expression associated with a variable evaluates to ``nothing``,
then that variable has the value ``nothing``, and may be used as such
in further expressions. Likewise, if the expression evaluates to
``default``, then the variable has the value ``default``, and may be
used as such in further expressions.

You can define two different kinds of variables: *local* and
*global*. When you define a local variable in a statement element, you
can only use that variable in that element and the elements it
contains. If you redefine a local variable in a contained element, the
new definition hides the outer element's definition within the inner
element. When you define a global variables, you can use it in any
element processed after the defining element. If you redefine a global
variable, you replace its definition for the rest of the template.

To set the definition scope of a variable, use the keywords ``local``
or ``global`` in front of the assignment. The default setting is
``local``; thus, in practice, only the ``global`` keyword is used.

.. note:: If you want to include a semicolon (";") in an expression, it
          must be escaped by doubling it (";;") [1]_.

Examples
~~~~~~~~

Defining a variable::

        tal:define="company_name 'Zope Corp, Inc.'"

Defining two variables, where the second depends on the first::

        tal:define="mytitle context.title; tlen len(mytitle)"


``tal:switch`` and ``tal:case``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Defines a switch clause.

::

  <ul tal:switch="len(items) % 2">
    <li tal:case="True">odd</li>
    <li tal:case="False">even</li>
  </ul>

Syntax
~~~~~~

``tal:case`` and ``tal:switch`` syntax::

    argument ::= expression

Description
~~~~~~~~~~~

The *switch* and *case* construct is a short-hand syntax for
evaluating a set of expressions against a parent value.

The ``tal:switch`` statement is used to set a new parent value and the
``tal:case`` statement works like a condition and only allows content
if the expression matches the value.

Note that if the case expression is the symbol ``default``, it always
matches the switch.

.. note:: These statements are only available in Chameleon 2.x and not
          part of the ZPT specification.

Examples
~~~~~~~~

::

  <ul tal:switch="item.type">
    <li tal:case="'document'">
      Document
    </li>
    <li tal:case="'folder'">
      Folder
    </li>
  </ul>

Note that any and all cases that match the switch will be included.


``tal:omit-tag``
^^^^^^^^^^^^^^^^

Removes an element, leaving its contents.

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

``tal:repeat``
^^^^^^^^^^^^^^

Repeats an element.

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

Repeat variables
~~~~~~~~~~~~~~~~~

You use repeat variables to access information about the current
repetition (such as the repeat index).  The repeat variable has the
same name as the local variable, but is only accessible through the
built-in variable named ``repeat``.

The following information is available from the repeat variable:

==================  ==============
 Attribute           Description
==================  ==============
``index``           Repetition number, starting from zero.
``number``          Repetition number, starting from one.
``even``            True for even-indexed repetitions (0, 2, 4, ...).
``odd``             True for odd-indexed repetitions (1, 3, 5, ...).
``start``           True for the starting repetition (index 0).
``end``             True for the ending, or final, repetition.
``first``           True for the first item in a group - see note below
``last``            True for the last item in a group - see note below
``length``          Length of the sequence, which will be the total number of repetitions.
``letter``          Repetition number as a lower-case letter: "a" - "z", "aa" - "az", "ba" - "bz", ..., "za" - "zz", "aaa" - "aaz", and so forth.
``Letter``          Upper-case version of *letter*.
``roman``           Repetition number as a lower-case roman numeral: "i", "ii", "iii", "iv", "v", etc.
``Roman``           Upper-case version of *roman*.
==================  ==============

You can access the contents of the repeat variable using either
dictionary- or attribute-style access, e.g. ``repeat['item'].start``
or ``repeat.item.start``.

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

``tal:replace``
^^^^^^^^^^^^^^^

Replaces an element.

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

.. _tales:

Expressions (TALES)
###################

The *Template Attribute Language Expression Syntax* (TALES) standard
describes expressions that supply :ref:`tal` and
:ref:`metal` with data.  TALES is *one* possible expression
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

Types
-----

These are the available TALES expression types:

=============  ==============
 Prefix        Description
=============  ==============
``exists``     Evaluate the result inside an exception handler; if one of the exceptions ``AttributeError``, ``LookupError``, ``TypeError``, ``NameError``, or ``KeyError`` is raised during evaluation, the result is ``False``, otherwise ``True``. Note that the original result is discarded in any case.
``import``     Import a global symbol using dotted notation.
``load``       Load a template relative to the current template or absolute.
``not``        Negate the expression result
``python``     Evaluate a Python expression
``string``     Format a string
``structure``  Wraps the expression result as *structure*.
=============  ==============

.. note:: The default expression type is ``python``.

.. warning:: The Zope reference engine defaults to a ``path``
             expression type, which is closely tied to the Zope
             framework. This expression is not implemented in
             Chameleon (but it's available in a Zope framework
             compatibility package).

There's a mechanism to allow fallback to alternative expressions, if
one should fail (raise an exception). The pipe character ('|') is used
to separate two expressions::

  <div tal:define="page request.GET['page'] | 0">

This mechanism applies only to the ``python`` expression type, and by
derivation ``string``.

.. _tales_built_in_names:

``python``
^^^^^^^^^^

Evaluates a Python expression.

Syntax
~~~~~~

Python expression syntax::

        Any valid Python language expression

Description
~~~~~~~~~~~

Python expressions are executed natively within the translated
template source code. There is no built-in security apparatus.

``string``
^^^^^^^^^^

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

.. _import-expression:

``import``
^^^^^^^^^^

Imports a module global.

.. _structure-expression:

``structure``
^^^^^^^^^^^^^

Wraps the expression result as *structure*: The replacement text is
inserted into the document without escaping, allowing HTML/XML markup
to be inserted.  This can break your page if the text contains
unanticipated markup (eg.  text submitted via a web form), which is
the reason that it is not the default.

.. _load-expression:

``load``
^^^^^^^^

Loads a template instance.

Syntax
~~~~~~

Load expression syntax::

         Relative or absolute file path

Description
~~~~~~~~~~~

The template will be loaded using the same template class as the
calling template.

Examples
~~~~~~~~

Loading a template and using it as a macro::

  <div tal:define="master load: ../master.pt" metal:use-macro="master" />


Built-in names
--------------

These are the names always available in the TALES expression namespace:

- ``default`` - special value used to specify that existing text or attributes should not be replaced. See the documentation for individual TAL statements for details on how they interpret *default*.

- ``repeat`` - the *repeat* variables; see :ref:`tal_repeat` for more
  information.

- ``template`` - reference to the template which was first called; this symbol is carried over when using macros.

- ``macros`` - reference to the macros dictionary that corresponds to the current template.


.. _metal:

Macros (METAL)
##############

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

Namespace
---------

The METAL namespace URI and recommended alias are currently defined
as::

        xmlns:metal="http://xml.zope.org/namespaces/metal"

Just like the TAL namespace URI, this URI is not attached to a web
page; it's just a unique identifier.  This identifier must be used in
all templates which use METAL.

Statements
----------

METAL defines a number of statements:

* ``metal:define-macro`` Define a macro.
* ``metal:use-macro`` Use a macro.
* ``metal:extend-macro`` Extend a macro.
* ``metal:define-slot`` Define a macro customization point.
* ``metal:fill-slot`` Customize a macro.

Although METAL does not define the syntax of expression non-terminals,
leaving that up to the implementation, a canonical expression syntax
for use in METAL arguments is described in TALES Specification.

``define-macro``
^^^^^^^^^^^^^^^^

Defines a macro.

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
          Copyright 2011, <em>Foobar</em> Inc.
        </p>

``define-slot``
^^^^^^^^^^^^^^^

Defines a macro customization point.

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

``fill-slot``
^^^^^^^^^^^^^

Customize a macro.

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

        <p metal:use-macro="container['master.html'].macros.hello">
          Hello <b metal:fill-slot="name">Kevin Bacon</b>
        </p>

``use-macro``
^^^^^^^^^^^^^

Use a macro.

Syntax
~~~~~~

``metal:use-macro`` syntax::

        argument ::= expression

Description
~~~~~~~~~~~

The ``metal:use-macro`` statement replaces the statement element with
a macro. The statement expression describes a macro definition.

.. note:: In Chameleon the expression may point to a template instance; in this case it will be rendered in its entirety.

``extend-macro``
^^^^^^^^^^^^^^^^

Extends a macro.

Syntax
~~~~~~

``metal:extend-macro`` syntax::

        argument ::= expression

Description
~~~~~~~~~~~

To extend an existing macro, choose a name for the macro and add a
define-macro attribute to a document element with the name as the
argument. Add an extend-macro attribute to the document element with
an expression referencing the base macro as the argument. The
extend-macro must be used in conjunction with define-macro, and must
not be used with use-macro. The element's subtree is the macro
body.

Examples
~~~~~~~~

::

        <div metal:define-macro="page-header"
             metal:extend-macro="standard_macros['page-header']">
          <div metal:fill-slot="breadcrumbs">
            You are here:
            <div metal:define-slot="breadcrumbs"/>
          </div>
        </div>


.. _i18n:

Translation (I18N)
##################

Translation of template contents and attributes is supported via the
``i18n`` namespace and message objects.

Messages
--------

The translation machinery defines a message as *any object* which is
not a string or a number and which does not provide an ``__html__``
method.

When any such object is inserted into the template, the translate
function is invoked first to see if it needs translation. The result
is always coerced to a native string before it's inserted into the
template.

Translation function
--------------------

The simplest way to hook into the translation machinery is to provide
a translation function to the template constructor or at
render-time. In either case it should be passed as the keyword
argument ``translate``.

The function has the following signature:

.. code-block:: python

   def translate(msgid, domain=None, mapping=None, context=None, target_language=None, default=None):
       ...

The result should be a string or ``None``. If another type of object
is returned, it's automatically coerced into a string.

If `zope.i18n <http://pypi.python.org/pypi/zope.i18n>`_ is available,
the translation machinery defaults to using its translation
function. Note that this function requires messages to conform to the
message class from `zope.i18nmessageid
<http://pypi.python.org/pypi/zope.i18nmessageid>`_; specifically,
messages must have attributes ``domain``, ``mapping`` and
``default``. Example use:

.. code-block:: python

   from zope.i18nmessageid import MessageFactory
   _ = MessageFactory("food")

   apple = _(u"Apple")

There's currently no further support for other translation frameworks.

Using Zope's translation framework
-----------------------------------

The translation function from ``zope.i18n`` relies on *translation
domains* to provide translations.

These are components that are registered for some translation domain
identifier and which implement a ``translate`` method that translates
messages for that domain.

.. note:: To register translation domain components, the Zope Component Architecture must be used (see `zope.component <http://pypi.python.org/pypi/zope.component>`_).

The easiest way to configure translation domains is to use the the
``registerTranslations`` ZCML-directive; this requires the use of the
`zope.configuration <http://pypi.python.org/pypi/zope.configuration>`_
package. This will set up translation domains and gettext catalogs
automatically:

.. code-block:: xml

  <configure xmlns="http://namespaces.zope.org/zope"
             xmlns:i18n="http://xml.zope.org/namespaces/i18n">

     <i18n:registerTranslations directory="locales" />

  </configure>

The ``./locales`` directory must follow a particular directory
structure:

.. code-block:: bash

  ./locales/en/LC_MESSAGES
  ./locales/de/LC_MESSAGES
  ...

In each of the ``LC_MESSAGES`` directories, one `GNU gettext
<http://en.wikipedia.org/wiki/GNU_gettext>`_ file in the ``.po``
format must be present per translation domain:

.. code-block:: po

  # ./locales/de/LC_MESSAGES/food.po

  msgid ""
  msgstr ""
  "MIME-Version: 1.0\n"
  "Content-Type: text/plain; charset=UTF-8\n"
  "Content-Transfer-Encoding: 8bit\n"

  msgid "Apple"
  msgstr "Apfel"

It may be necessary to compile the message catalog using the
``msgfmt`` utility. This will produce a ``.mo`` file.

Translation domains without gettext
-----------------------------------

The following example demonstrates how to manually set up and
configure a translation domain for which messages are provided
directly::

  from zope import component
  from zope.i18n.simpletranslationdomain import SimpleTranslationDomain

  food = SimpleTranslationDomain("food", {
      ('de', u'Apple'): u'Apfel',
      })

  component.provideUtility(food, food.domain)

An example of a custom translation domain class::

  from zope import interface

  class TranslationDomain(object):
       interface.implements(ITranslationDomain)

       def translate(self, msgid, mapping=None, context=None,
                    target_language=None, default=None):

           ...

  component.provideUtility(TranslationDomain(), name="custom")

This approach can be used to integrate other translation catalog
implementations.

.. highlight:: xml

Namespace
---------

The ``i18n`` namespace URI and recommended prefix are currently
defined as::

  xmlns:i18n="http://xml.zope.org/namespaces/i18n"

This is not a URL, but merely a unique identifier.  Do not expect a
browser to resolve it successfully.

Statements
----------

The allowable ``i18n`` statements are:

- ``i18n:translate``
- ``i18n:domain``
- ``i18n:source``
- ``i18n:target``
- ``i18n:name``
- ``i18n:attributes``
- ``i18n:data``

``i18n:translate``
^^^^^^^^^^^^^^^^^^

This attribute is used to mark units of text for translation.  If this
attribute is specified with an empty string as the value, the message
ID is computed from the content of the element bearing this attribute.
Otherwise, the value of the element gives the message ID.

``i18n:domain``
^^^^^^^^^^^^^^^

The ``i18n:domain`` attribute is used to specify the domain to be used
to get the translation.  If not specified, the translation services
will use a default domain.  The value of the attribute is used
directly; it is not a TALES expression.

``i18n:source``
^^^^^^^^^^^^^^^

The ``i18n:source`` attribute specifies the language of the text to be
translated.  The default is ``nothing``, which means we don't provide
this information to the translation services.


``i18n:target``
^^^^^^^^^^^^^^^

The ``i18n:target`` attribute specifies the language of the
translation we want to get.  If the value is ``default``, the language
negotiation services will be used to choose the destination language.
If the value is ``nothing``, no translation will be performed; this
can be used to suppress translation within a larger translated unit.
Any other value must be a language code.

The attribute value is a TALES expression; the result of evaluating
the expression is the language code or one of the reserved values.

.. note:: ``i18n:target`` is primarily used for hints to text
   extraction tools and translation teams.  If you had some text that
   should only be translated to e.g. German, then it probably
   shouldn't be wrapped in an ``i18n:translate`` span.

``i18n:name``
^^^^^^^^^^^^^

Name the content of the current element for use in interpolation
within translated content.  This allows a replaceable component in
content to be re-ordered by translation.  For example::

    <span i18n:translate=''>
      <span tal:replace='context.name' i18n:name='name' /> was born in
      <span tal:replace='context.country_of_birth' i18n:name='country' />.
    </span>

would cause this text to be passed to the translation service::

    "${name} was born in ${country}."

``i18n:attributes``
^^^^^^^^^^^^^^^^^^^

This attribute will allow us to translate attributes of HTML tags,
such as the ``alt`` attribute in the ``img`` tag. The
``i18n:attributes`` attribute specifies a list of attributes to be
translated with optional message IDs for each; if multiple attribute
names are given, they must be separated by semicolons.  Message IDs
used in this context must not include whitespace.

Note that the value of the particular attributes come either from the
HTML attribute value itself or from the data inserted by
``tal:attributes``.

If an attibute is to be both computed using ``tal:attributes`` and
translated, the translation service is passed the result of the TALES
expression for that attribute.

An example::

    <img src="http://foo.com/logo" alt="Visit us"
         tal:attributes="alt context.greeting"
         i18n:attributes="alt"
         >

In this example, we let ``tal:attributes`` set the value of the ``alt``
attribute to the text "Stop by for a visit!".  This text will be
passed to the translation service, which uses the result of language
negotiation to translate "Stop by for a visit!" into the requested
language.  The example text in the template, "Visit us", will simply
be discarded.

Another example, with explicit message IDs::

    <img src="../icons/uparrow.png" alt="Up"
         i18n:attributes="src up-arrow-icon; alt up-arrow-alttext"
         >

Here, the message ID ``up-arrow-icon`` will be used to generate the
link to an icon image file, and the message ID 'up-arrow-alttext' will
be used for the "alt" text.

``i18n:data``
^^^^^^^^^^^^^

Since TAL always returns strings, we need a way in ZPT to translate
objects, one of the most obvious cases being ``datetime`` objects. The
``data`` attribute will allow us to specify such an object, and
``i18n:translate`` will provide us with a legal format string for that
object.  If ``data`` is used, ``i18n:translate`` must be used to give
an explicit message ID, rather than relying on a message ID computed
from the content.

Relation with TAL processing
----------------------------

The attributes defined in the ``i18n`` namespace modify the behavior
of the TAL interpreter for the ``tal:attributes``, ``tal:content``,
``tal:repeat``, and ``tal:replace`` attributes, but otherwise do not
affect TAL processing.

Since these attributes only affect TAL processing by causing
translations to occur at specific times, using these with a TAL
processor which does not support the ``i18n`` namespace degrades well;
the structural expectations for a template which uses the ``i18n``
support is no different from those for a page which does not.  The
only difference is that translations will not be performed in a legacy
processor.

Relation with METAL processing
-------------------------------

When using translation with METAL macros, the internationalization
context is considered part of the specific documents that page
components are retrieved from rather than part of the combined page.
This makes the internationalization context lexical rather than
dynamic, making it easier for a site builder to understand the
behavior of each element with respect to internationalization.

Let's look at an example to see what this means::

    <html i18n:translate='' i18n:domain='EventsCalendar'
          metal:use-macro="container['master.html'].macros.thismonth">

      <div metal:fill-slot='additional-notes'>
        <ol tal:condition="context.notes">
          <li tal:repeat="note context.notes">
             <tal:block tal:omit-tag=""
                        tal:condition="note.heading">
               <strong tal:content="note.heading">
                 Note heading goes here
               </strong>
               <br />
             </tal:block>
             <span tal:replace="note/description">
               Some longer explanation for the note goes here.
             </span>
          </li>
        </ol>
      </div>

    </html>

And the macro source::

    <html i18n:domain='CalendarService'>
      <div tal:replace='python:DateTime().Month()'
           i18n:translate=''>January</div>

      <!-- really hairy TAL code here ;-) -->

      <div define-slot="additional-notes">
        Place for the application to add additional notes if desired.
      </div>

    </html>

Note that the macro is using a different domain than the application
(which it should be).  With lexical scoping, no special markup needs
to be applied to cause the slot-filler in the application to be part
of the same domain as the rest of the application's page components.
If dynamic scoping were used, the internationalization context would
need to be re-established in the slot-filler.


Extracting translatable message
-------------------------------

Translators use `PO files
<http://www.gnu.org/software/hello/manual/gettext/PO-Files.html>`_
when translating messages. To create and update PO files you need to
do two things: *extract* all messages from python and templates files
and store them in a ``.pot`` file, and for each language *update* its
``.po`` file.  Chameleon facilitates this by providing extractors for
`Babel <http://babel.edgewall.org/>`_.  To use this you need modify
``setup.py``. For example:

.. code-block:: python

   from setuptools import setup

   setup(name="mypackage",
         install_requires = [
               "Babel",
               ],
         message_extractors = { "src": [
               ("**.py",   "chameleon_python", None ),
               ("**.pt",   "chameleon_xml", None ),
               ]},
         )

This tells Babel to scan the ``src`` directory while using the
``chameleon_python`` extractor for all ``.py`` files and the
``chameleon_xml`` extractor for all ``.pt`` files.

You can now use Babel to manage your PO files:

.. code-block:: bash

   python setup.py extract_messages --output-file=i18n/mydomain.pot
   python setup.py update_catalog \
             -l nl \
             -i i18n/mydomain.pot \
             -o i18n/nl/LC_MESSAGES/mydomain.po
   python setup.py compile_catalog \
             --directory i18n --locale nl

You can also configure default options in a ``setup.cfg`` file. For example::

   [compile_catalog]
   domain = mydomain
   directory = i18n
   
   [extract_messages]
   copyright_holder = Acme Inc.
   output_file = i18n/mydomain.pot
   charset = UTF-8

   [init_catalog]
   domain = mydomain
   input_file = i18n/mydomain.pot
   output_dir = i18n

   [update_catalog]
   domain = mydomain
   input_file = i18n/mydomain.pot
   output_dir = i18n
   previous = true

You can now use the Babel commands directly::

   python setup.py extract_messages
   python setup.py update_catalog
   python setup.py compile_catalog


${...} operator
###############

The ``${...}`` notation is short-hand for text insertion. The
Python-expression inside the braces is evaluated and the result
included in the output (all inserted text is escaped by default):

.. code-block:: html

  <div id="section-${index + 1}">
    ${content}
  </div>

To escape this behavior, prefix the notation with a backslash
character: ``\${...}``.

Note that if an object implements the ``__html__`` method, the result
of this method will be inserted as-is (without XML escaping).

Markup comments
###############

You can apply the "!" and "?" modifiers to change how comments are
processed:

Drop

  ``<!--! This comment will be dropped from output -->``

Verbatim

  ``<!--? This comment will be included verbatim -->``

  That is, evaluation of ``${...}`` expressions is disabled if the
  comment opens with the "?" character.


.. _new-features:

Language extensions
###################

The page template language as implemented in the Chameleon library
comes with a number of new features. Some take inspiration from
`Genshi <http://genshi.edgewall.org/>`_.

    *New expression types*

       The :ref:`structure <structure-expression>` expression wraps an
       expression result as *structure*::

         <div>${structure: body.text}</div>

       The :ref:`import <import-expression>` expression imports module globals::

         <div tal:define="compile import: re.compile">
           ...
         </div>

       This :ref:`load <load-expression>` expression loads templates
       relative to the current template::

         <div tal:define="compile load: main.pt">
           ...
         </div>

    *Tuple unpacking*

       The ``tal:define`` and ``tal:repeat`` statements supports tuple
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


Incompatibilities and differences
#################################

There are a number of incompatibilities and differences between the
Chameleon language implementation and the Zope reference
implementation (ZPT):

    *Default expression*

       The default expression type is Python.

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

Notes
#####

.. [1] This has been changed in 2.x. Previously, it was up to the
       expression engine to parse the expression values including any
       semicolons and since for instance Python-expressions can never
       end in a semicolon, it was possible to clearly distinguish
       between the different uses of the symbol, e.g.

       ::

         tal:define="text 'Hello world; goodbye world'"

       The semicolon appearing in the definition above is part of the
       Python-expression simply because it makes the expression
       valid. Meanwhile:

       ::

         tal:define="text1 'Hello world'; text2 'goodbye world'"

       The semicolon here must denote a second variable definition
       because there is no valid Python-expression that includes it.

       While this behavior works well in practice, it is incompatible
       with the reference specification, and also blurs the interface
       between the compiler and the expression engine. In 2.x we
       therefore have to escape the semicolon by doubling it (as
       defined by the specification):

       ::

         tal:define="text 'Hello world;; goodbye world'"

