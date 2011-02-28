Chameleon
=========

Chameleon is an HTML/XML template language compiler.

It includes a feature-complete engine for the Zope Page Templates
(ZPT) language.

Templates are compiled (or *translated*) into Python source code. This
means that logic and control flow is evaluated inline without
additional function calls or run-time decisions, decimating the
template engine overhead. In real-world applications such as `Plone
<http://www.plone.org>`_, this translates to 30-60% better response
times.

*How does it look?* --- here's an example:

.. code-block:: html

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

The included ZPT template engine can be used completely on its own. It
has no hard library dependency. Meanwhile, the translation interface
(internationalization) is compatible with the `zope.i18n
<http://pypi.python.org/pypi/zope.i18n>`_ package and is recommended
for projects that require translation.

While ZPT is an *attribute-based* language where XML attributes (with
special prefixes) control program flow, the Chameleon implementation
comes with support for the ``${...}`` inline expression operator. This
also works in attributes:

.. code-block:: html

  <div id="section-${index}">
    ...
  </div>

The string inside the operator is evaluated using the *expression
engine*. In Chameleon, the default expression is simply: Python.

License
-------

This software is made available under a BSD-like license.

Compatibility
-------------

Chameleon runs on all Python platforms from 2.5 and up (including
Python 3.x).

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

To get started right away using Chameleon, visit the :ref:`getting started <getting-started-with-zpt>` section.

To read more about integration into web frameworks see the section on :ref:`framework integration <framework-integration>`.

Contents
========

.. toctree::
   :maxdepth: 2

   zpt.rst
   i18n.rst
   integration.rst
   configuration.rst

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

