Chameleon
=========

Chameleon is an HTML/XML template engine for `Python
<http://www.python.org>`_.

It's designed to generate the document output of a web application,
typically HTML markup or XML.

The language used is *page templates*, originally a `Zope
<http://www.zope.org>`_ invention [1]_, but available here as a
:ref:`standalone library <no-dependencies>` that you can use in any
script or application running Python 2.5 and up (including 3.x and
`pypy <http://pypy.org>`_). It comes with a set of :ref:`new features
<new-features>`, too.

The template engine compiles templates into Python byte-code and is optimized
for speed. For a complex template language, the performance is
:ref:`very good <fast>`.

  *Found a bug?* Please report issues to the `issue tracker <http://github.com/malthe/chameleon/issues>`_.

  *Need help?* Post to the Pylons `discussion list <http://groups.google.com/group/pylons-discuss/>`_ or join the ``#pyramid`` channel on `Freenode IRC <http://freenode.net/>`_.

Getting the code
----------------

You can `download <http://pypi.python.org/pypi/Chameleon#downloads>`_ the
package from the Python package index or install the latest release
using setuptools or the newer `distribute
<http://packages.python.org/distribute/>`_ (required for Python 3.x)::

  $ easy_install Chameleon

.. _no-dependencies:

There are no required library dependencies on Python 2.7 and up
[2]_. On 2.5 and 2.6, the `ordereddict
<http://pypi.python.org/pypi/ordereddict>`_ and `unittest2
<http://pypi.python.org/pypi/unittest2>`_ packages are set as
dependencies.

The project is hosted in a `GitHub repository
<http://github.com/malthe/chameleon>`_. Code contributions are
welcome. The easiest way is to use the `pull request
<http://help.github.com/pull-requests/>`_ interface.


Introduction
------------

The *page templates* language is used within your document structure
as special element attributes and text markup. Using a set of simple
language constructs, you control the document flow, element
repetition, text replacement and translation.

.. note:: If you've used page templates in a Zope environment previously, note that Chameleon uses Python as the default expression language (instead of *path* expressions).

The basic language (known as the *template attribute language* or TAL)
is simple enough to grasp from an example:

.. code-block:: genshi

  <html>
    <body>
      <h1>Hello, ${'world'}!</h1>
      <table>
        <tr tal:repeat="row 'apple', 'banana', 'pineapple'">
          <td tal:repeat="col 'juice', 'muffin', 'pie'">
             ${row.capitalize()} ${col}
          </td>
        </tr>
      </table>
    </body>
  </html>

The ``${...}`` notation is short-hand for text insertion [3]_. The
Python-expression inside the braces is evaluated and the result
included in the output. By default, the string is escaped before
insertion. To avoid this, use the ``structure:`` prefix:

.. code-block:: genshi

  <div>${structure: ...}</div>

Note that if the expression result is an object that implements an
``__html__()`` method [4]_, this method will be called and the result
treated as "structure". An example of such an object is the
``Markup`` class that's included as a utility::

  from chameleon.utils import Markup
  username = "<tt>%s</tt>" % username

The macro language (known as the *macro expansion language* or METAL)
provides a means of filling in portions of a generic template.

On the left, the macro template; on the right, a template that loads
and uses the macro, filling in the "content" slot:

.. code-block:: genshi

  <html xmlns="http://www.w3.org/1999/xhtml">             <metal:main use-macro="load: main.pt">
    <head>                                                   <p metal:fill-slot="content">${structure: document.body}<p/>
      <title>Example &mdash; ${document.title}</title>    </metal:main>
    </head>
    <body>
      <h1>${document.title}</h1>

      <div id="content">
        <metal:content define-slot="content" />
      </div>
    </body>
  </html>

In the example, the expression type :ref:`load <load-expression>` is
used to retrieve a template from the file system using a path relative
to the calling template.

The METAL system works with TAL such that you can for instance fill in
a slot that appears in a ``tal:repeat`` loop, or refer to variables
defined using ``tal:define``.

The third language subset is the translation system (known as the
*internationalization language* or I18N):

.. code-block:: genshi

  <html i18n:domain="example">

    ...

    <div i18n:translate="">
       You have <span i18n:name="amount">${round(amount, 2)}</span> dollars in your account.
    </div>

    ...

  </html>

Each translation message is marked up using ``i18n:translate`` and
values can be mapped using ``i18n:name``. Attributes are marked for
translation using ``i18n:attributes``. The template engine generates
`gettext <http://www.gnu.org/s/gettext/>`_ translation strings from
the markup::

  "You have ${amount} dollars in your account."

If you use a web framework such as `Pyramid
<https://docs.pylonsproject.org/docs/pyramid.html>`_, the translation
system is set up automatically and will negotiate on a *target
language* based on the HTTP request or other parameter. If not, then
you need to configure this manually.

Next steps
----------

This was just an introduction. There are a number of other basic
statements that you need to know in order to use the language. This is
all covered in the :ref:`language reference <language-reference>`.

If you're already familiar with the page template language, you can
skip ahead to the :ref:`getting started <getting-started-with-cpt>`
section to learn how to use the template engine in your code.

To learn about integration with your favorite web framework see the
section on :ref:`framework integration <framework-integration>`.

License
-------

This software is made available under a BSD-like license.


Contents
========

.. toctree::
   :maxdepth: 2

   library.rst
   reference.rst
   integration.rst
   configuration.rst

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Notes
=====

.. [1] The template language specifications and API for the Page
       Templates engine are based on Zope Page Templates (see in
       particular `zope.pagetemplate
       <http://pypi.python.org/pypi/zope.pagetemplate>`_). However,
       the Chameleon compiler and Page Templates engine is an entirely
       new codebase, packaged as a standalone distribution. It does
       require a Zope software environment.

.. [2] The translation system in Chameleon is pluggable and based on
       `gettext <http://www.gnu.org/s/gettext/>`_.
       There is built-in support for the `zope.i18n
       <http://pypi.python.org/pypi/zope.i18n>`_ package. If this
       package is installed, it will be used by default. The
       `translationstring
       <http://pypi.python.org/pypi/translationstring>`_ package
       offers some of the same helper and utility classes, without the
       Zope application interface.

.. [3] This syntax was taken from `Genshi <http://genshi.edgewall.org/>`_.

.. [4] See the `WebHelpers
       <https://docs.pylonsproject.org/projects/webhelpers/dev/modules/html/__init__.html>`_
       library which provide a simple wrapper around this method.
