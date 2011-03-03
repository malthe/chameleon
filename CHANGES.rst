Changes
=======

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
