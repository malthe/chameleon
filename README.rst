Overview
--------

Chameleon compiles templates to Python byte-code. It includes a
complete implementation of the Zope Page Templates (ZPT) language.

The engine itself performs 10-15 times better than the reference
implementation and real-world benchmarks show an overall performance
improvement in complex applications of 30-50%.

License
-------

This software is made available under the BSD license.

Development
-----------

The code is maintained in a subversion repository::

  svn://svn.repoze.org/svn/chameleon/trunk

If you want to contribute or need support, join #repoze on freenode
irc or write the `mailinglist <mailto:repoze-dev@lists.repoze.org>`_.

Languages
=========

An implementation of the Zope Page Templates language is included. The
Genshi language has been implemented and is currently maintained in a
separate package.

Zope Page Templates
-------------------

The ZPT implementation is largely compatible with the reference
implementation. Below is an overview of notable differences:

Default expression

   The default expression is ``python:``. Path expressions are not
   supported in the base package. The package introduces the
   ``import:`` expression which imports global names.

Tuple unpacking

   The ``tal:define`` and ``tal:repeat`` clauses supports tuple
   unpacking::

      tal:define="(a, b, c) [1, 2, 3]"

   The star character is not supported.

Dot-notation for dictionary lookups

   If attribute lookup fails (i.e. the dot operator), dictionary
   lookup is tried. The engine replaces attribute lookups with a call
   to a function that has the following body::

      try:
          return context.key
      except AttributeError:
          try:
              return context[key]
          except KeyError:
              raise AttributeError(key)

Interpolation is supported

   The Genshi expression interpolation syntax is supported outside
   tags and inside static attributes::

      <span class="hello-${'world'}">
         Hello, ${'world'}!
      </span>

Literal insertion

   If objects for insertion provide an ``__html__`` method, it will be
   called and the result inserted literally, without escaping.




