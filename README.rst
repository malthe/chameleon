Overview
========

Chameleon is an HTML/XML template language compiler.

The distribution comes with a complete template engine: Chameleon Page
Templates [1]_.

There are no external library dependencies [2]_. You can install it
using setuptools or the newer `distribute
<http://packages.python.org/distribute/>`_ (recommended)::

  $ easy_install Chameleon

Formatted `documentation <http://repoze.chameleon.org/docs/latest>`_
is available.

Platform
---------

This library has been successfully tested on the following platforms:

* Python 2.5, 2.6, 2.7
* Python 3.1, 3.2
* PyPy

What's New in 2.x
------------------

The 2.x series is a complete rewrite of the library and supports both
Python 2.5+ and Python 3.1+ with a single source code.

For most users it should be an easy upgrade, however note that at
present, there is no engine for the Genshi language.

New parser
~~~~~~~~~~

This series features a new parser, implemented in pure Python. It
parses both HTML and XML inputs (the previous parser relied on the
expat system library and was more strict about its input).

Language changes
~~~~~~~~~~~~~~~~

The 2.x engine matches the output of the reference implementation more
closely (usually exactly). There are less differences altogether; for
instance, the method of escaping TALES expression (usually a
semicolon) has been changed to match that of the reference
implementation.

This series also introduces a number of new language features:

1) Support for the ``tal:on-error`` from the reference specification
has been added.

2) Inspired by the Genshi language, a pair of new attributes has been
added: ``tal:switch`` and ``tal:case``, allowing flexible conditions.

Expression engine
~~~~~~~~~~~~~~~~~

The expression engine has been redesigned to make it easier to
understand and extend.

The engine is built on the ``ast`` module (available since Python 2.6;
backports included for Python 2.5).

Performance
~~~~~~~~~~~

The compiler output has been optimized for complex templates. For most
applications, the engine should perform similarly to the 1.x
series.

Very simple templates with tight loops (such as that of the "big
table" benchmark) will see a decrease in performance. The compiler is
optimized for dynamic variable scope and this lowers performance for
templates that require only a static scope.


License and Copyright
---------------------

This software is made available as-is under a BSD-like license [3]_
(see included copyright notice).


Notes
-----

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

.. [3] This software is licensed under the `Repoze
       <http://repoze.org/license.html>`_ license.
