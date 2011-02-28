Overview
========

Chameleon is an HTML/XML [1]_ template language compiler.

It includes a feature-complete engine for the Zope Page Templates
(ZPT) language.

The software is released on PyPi. To download and install the latest
release::

  $ easy-install -U Chameleon

Platforms
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

This software is made available as-is under a BSD-like license
[2]_ (see included copyright notice).

.. [1] There is currently no support for unstructured documents.

.. [2] Licensed under the `Repoze <http://repoze.org/license.html>`_
       license.
