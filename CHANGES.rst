Changes
=======

2.0-rc7 (2011-03-29)
--------------------

Bugfixes:

- Fixed issue with Python 2.5 compatibility AST. This affected at
  least PyPy 1.4.

Features:

- The ``auto_reload`` setting now defaults to the class value; the
  base template class gives a default value of
  ``chameleon.config.AUTO_RELOAD``. This change allows a subclass to
  provide a custom default value (such as an application-specific
  debug mode setting).


2.0-rc6 (2011-03-19)
--------------------

Features:

- Added support for ``target_language`` keyword argument to render
  method. If provided, the argument will be curried onto the
  translation function.

Bugfixes:

- The HTML entities 'lt', 'gt' and 'quot' appearing inside content
  subtition expressions are now translated into their native character
  values. This fixes an issue where you could not dynamically create
  elements using the ``structure`` (which is possible in ZPT). The
  need to create such structure stems from the lack of an expression
  interpolation operator in ZPT.

- Fixed duplicate file pointer issue with test suite (affected Windows
  platforms only). This fixes issue #9.
  [oliora]

- Use already open file using ``os.fdopen`` when trying to write out
  the module source. This fixes LP #731803.


2.0-rc5 (2011-03-07)
--------------------

Bugfixes:

- Fixed a number of issues concerning the escaping of attribute
  values:

  1) Static attribute values are now included as they appear in the
     source.

     This means that invalid attribute values such as ``"true &&
     false"`` are now left alone. It's not the job of the template
     engine to correct such markup, at least not in the default mode
     of operation.

  2) The string expression compiler no longer unescapes
     values. Instead, this is left to each expression
     compiler. Currently only the Python expression compiler unescapes
     its input.

  3) The dynamic escape code sequence now correctly only replaces
     ampersands that are part of an HTML escape format.

Imports:

- The page template classes and the loader class can now be imported
  directly from the ``chameleon`` module.

Features:

- If a custom template loader is not provided, relative paths are now
  resolved using ``os.abspath`` (i.e. to the current working
  directory).

- Absolute paths are normalized using ``os.path.normpath`` and
  ``os.path.expanduser``. This ensures that all paths are kept in
  their "canonical" form.


2.0-rc4 (2011-03-03)
--------------------

Bugfixes:

- Fixed an issue where the output of an end-to-end string expression
  would raise an exception if the expression evaluated to ``None`` (it
  should simply output nothing).

- The ``convert`` function (which is configurable on the template
  class level) now defaults to the ``translate`` function (at
  run-time).

  This fixes an issue where message objects were not translated (and
  thus converted to a string) using the a provided ``translate``
  function.

- Fixed string interpolation issue where an expression immediately
  succeeded by a right curly bracket would not parse.

  This fixes issue #5.

- Fixed error where ``tal:condition`` would be evaluated after
  ``tal:repeat``.

Features:

- Python expression is now a TALES expression. That means that the
  pipe operator can be used to chain two or more expressions in a
  try-except sequence.

  This behavior was ported from the 1.x series. Note that while it's
  still possible to use the pipe character ("|") in an expression, it
  must now be escaped.

- The template cache can now be shared by multiple processes.


2.0-rc3 (2011-03-02)
--------------------

Bugfixes:

- Fixed ``atexit`` handler.

  This fixes issue #3.

- If a cache directory is specified, it will now be used even when not
  in debug mode.

- Allow "comment" attribute in the TAL namespace.

  This fixes an issue in the sense that the reference engine allows
  any attribute within the TAL namespace. However, only "comment" is
  in common use.

- The template constructor now accepts a flag ``debug`` which puts the
  template *instance* into debug-mode regardless of the global
  setting.

  This fixes issue #1.

Features:

- Added exception handler for exceptions raised while evaluating an
  expression.

  This handler raises (or attempts to) a new exception of the type
  ``RenderError``, with an additional base class of the original
  exception class. The string value of the exception is a formatted
  error message which includes the expression that caused the
  exception.

  If we are unable to create the exception class, the original
  exception is re-raised.

2.0-rc2 (2011-02-28)
--------------------

- Fixed upload issue.

2.0-rc1 (2011-02-28)
--------------------

- Initial public release. See documentation for what's new in this
  series.
