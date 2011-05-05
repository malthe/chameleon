Chameleon Page Templates
========================

Chameleon is an HTML/XML template engine for `Python
<http://www.python.org>`_.

It's designed to generate the document output of a web application,
typically HTML markup or XML.

The language used is *page templates*, originally a `Zope
<http://www.zope.org>`_ invention [1]_, but now available in a
:ref:`fast <fast>`, :ref:`independent <no-dependencies>`
implementation --- it comes with a moderate set of :ref:`new features
<new-features>`, too.

You can use it in any Python web application with just about any
version of Python (2.5 and up, including 3.x and `pypy
<http://pypy.org>`_).

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
[2]_. On 2.5 and 2.6 the `ordereddict
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

The basic language (knows as the *template attribute language* or TAL)
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
included in the output (all inserted text is escaped by default):

.. code-block:: html

  <div id="section-${index + 1}">
    ${content}
  </div>

Note that to insert the value of a symbol, the curly braces can be
omitted entirely: ``Hello, $name!``.

What's New in 2.x
------------------

This version is a complete rewrite of the library. The biggest
implications are the added compatibility for newer versions of Python
(although support for 2.4 has been dropped), but also that there is
currently no language implementation for Genshi.

For most users of the page templates implementation, it should be an
easy upgrade. See the complete list of :ref:`changes <whats-new>` for
more information.

License
-------

This software is made available under a BSD-like license.

Next steps
----------

The :ref:`language reference <language-reference>` is a not only a
handy reference, but also doubles as a general introduction to the
language with plenty of examples.

If you're already familiar with page templates, you can skip ahead
to the :ref:`getting started <getting-started-with-cpt>` section to
learn how to use them in your code.

To learn about integration with your favorite web framework see the
section on :ref:`framework integration <framework-integration>`.


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
       `gettext <http://www.gnu.org/software/gettext/gettext.html>`_.
       There is built-in support for the `zope.i18n
       <http://pypi.python.org/pypi/zope.i18n>`_ package. If this
       package is installed, it will be used by default. The
       `translationstring
       <http://pypi.python.org/pypi/translationstring>`_ package
       offers some of the same helper and utility classes, without the
       Zope application interface.

.. [3] This syntax was taken from `Genshi <http://genshi.edgewall.org/>`_.
