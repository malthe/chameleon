.. Chameleon documentation master file, created by
   sphinx-quickstart on Sun Nov  1 16:08:00 2009.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Chameleon
=========

Chameleon is an XML attribute language template compiler. It comes
with implementations for the Zope Page Templates (ZPT) and Genshi
languages.

The engine compiles templates into Python byte-code. This results in
performance which is on average 10-15 times better than implementation
which use runtime interpretation. Real-world application benchmarks
show an overall performance improvement in complex applications of
30-50%.

Releases are available on PyPi. To get the latest release::

  $ easy-install -U Chameleon

License
-------

This software is made available under the BSD license.

Development
-----------

To report bugs, use the `Chameleon bug tracker
<https://bugs.launchpad.net/chameleon>`_. If you've got questions that
aren't answered by this documentation, please contact the `Repoze
mailinglist <http://lists.repoze.org/listinfo/repoze-dev>`_.

Browse and check out tagged and trunk versions of :mod:`Chameleon` via
the `Repoze Subversion repository
<http://svn.repoze.org/chameleon/>`_.  To check out the trunk via
Subversion, use this command::

  $ svn co svn://svn.repoze.org/chameleon/trunk chameleon

Related projects
----------------

An HTML-based language which integrates with ZPT (see `chameleon.html
<http://pypi.python.org/pypi/chameleon.html>`_)::

  $ svn co svn://svn.repoze.org/chameleon.html/trunk chameleon-html

Contents
========

.. toctree::
   :maxdepth: 2

   zpt.rst
   genshi.rst
   i18n.rst
   config.rst

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

