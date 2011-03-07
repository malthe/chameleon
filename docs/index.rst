Chameleon
=========

Chameleon is an HTML/XML template language compiler.

The distribution comes with a complete template engine: Chameleon Page
Templates [1]_.

There are no external library dependencies [2]_. You can install it
using setuptools or the newer `distribute
<http://packages.python.org/distribute/>`_ (recommended)::

  $ easy_install Chameleon


Introduction
------------

*Page Templates* is an XML-based template engine. The only general
implication of this is that the engine knows about the structure of
the document: elements, attributes, comments and so on.

In addition, the template language is mostly attribute-based, such
that XML attributes (with special prefixes) are used to program
template logic and behavior.

This might sound frightening or even off-putting; in practice, it's
both simple to read and understand. It also looks "right" in your
editor:

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

There's a short-hand syntax available for content substitution: The
``${...}`` inline expression operator [3]_ evaluates the expression
inside and includes the result in the output. It follows the usual
document escape logic and works in both content and attributes:

.. code-block:: html

  <div id="section-${index + 1}">
    ${content}
  </div>

Note that for simple variable expressions, the curly braces can be
omitted entirely.

Features
--------

Here's an itemized overview that highlights some of the features in
Chameleon.

*Fast*

    Template files are compiled (or *translated*) into Python source
    code. This means that logic and control flow are evaluated inline
    without additional function calls or run-time decisions,
    decimating the template engine overhead. In real-world
    applications such as `Plone <http://www.plone.org>`_, this
    translates to 30-60% better response times.

*Flexibile*

    The template source code is read by a custom lexer and parser that
    stays out of your way as much as possible. The output should match
    the input and we try to leave out surprises.

*Compatible*

    The Chameleon *Page Templates* engine is compatible with few
    changes to the Zope Page Templates engine (in various flavors)
    which are used in many enterprise systems including the `Plone
    <http://www.plone.org>`_ content management system.

*Tested*

    The distribution comes with a complete test suite. Before any
    release, we make sure the software runs perfectly on all supported
    platforms.

License
-------

This software is made available under a BSD-like license.

Compatibility
-------------

Chameleon runs on all Python platforms from 2.5 and up (including
Python 3.1+).

Development
-----------

To report bugs, please use the `issue tracker
<http://github.com/malthe/chameleon/issues>`_.

If you've got questions that aren't answered by this documentation,
post them to the `Repoze Mailing List
<http://lists.repoze.org/listinfo/repoze-dev>`_. You can also log on
to ``#repoze`` on `Freenode IRC <http://freenode.net/>`_ and chat.

Browse and check out tagged and trunk versions of this software using
the `Github Repository
<http://github.com/malthe/chameleon/>`_. In read-only mode::

  $ git clone git://github.com/malthe/chameleon.git

Contributions are welcome. The easiest way to get started is to create
a fork of the project and use the `pull request
<http://help.github.com/pull-requests/>`_ interface.

What next?
----------

To get started right away using Chameleon, visit the :ref:`getting started <getting-started-with-cpt>` section.

To read more about integration into web frameworks see the section on :ref:`framework integration <framework-integration>`.

Contents
========

.. toctree::
   :maxdepth: 2

   pt.rst
   i18n.rst
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


.. [2] The string translation interface is based on the `gettext
       <http://www.gnu.org/software/gettext/gettext.html>`_
       library. Chameleon comes with built-in support for the
       `zope.i18n <http://pypi.python.org/pypi/zope.i18n>`_ package
       which includes a translation framework
       (internationalization). If this package is installed, it will
       be used as the default translation framework. It is trivial to
       provide a custom translation function, however.


.. [3] This syntax was taken from `Genshi <http://genshi.edgewall.org/>`_.
