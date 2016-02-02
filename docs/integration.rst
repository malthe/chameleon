.. _framework-integration:

Integration
===========

Integration with Chameleon is available for a number of popular web
frameworks. The framework will usually provide loading mechanisms and
translation (internationalization) configuration.

Pyramid
-------

`pyramid_chameleon
<http://docs.pylonsproject.org/projects/pyramid-chameleon/en/latest/>`_
is a set of bindings that make templates written for the Chameleon
templating system work under the Pyramid web framework.

Zope 2 / Plone
--------------

Install the `five.pt <http://pypi.python.org/pypi/five.pt>`_ package
to replace the reference template engine (globally).

Zope Toolkit (ZTK)
------------------

Install the `z3c.pt <http://pypi.python.org/pypi/z3c.pt>`_ package for
applications based on the `Zope Toolkit
<http://docs.zope.org/zopetoolkit/>`_ (ZTK). Note that you need to
explicit use the template classes from this package.

Grok
----

Support for the `Grok <http://grok.zope.org/>`_ framework is available
in the `grokcore.chameleon
<http://pypi.python.org/pypi/grokcore.chameleon>`_ package.

This package will setup Grok's policy for templating integration and
associate the Chameleon template components for the ``.cpt`` template
filename extension.

Django
------

Install the `django-chameleon-templates <https://bitbucket.org/kveroneau/django-chameleon-templates>`_ app to enable Chameleon as a template engine.
