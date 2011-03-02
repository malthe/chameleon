Changes
=======

Bugfixes:

- Allow "comment" attribute in the TAL namespace.

  This fixes an issue in the sense that the reference engine allows
  any attribute within the TAL namespace. However, only "comment" is
  in common use.

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
