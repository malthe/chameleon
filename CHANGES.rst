Changes
=======

In next release ...

- Fixed issue where a ``metal:fill-slot`` would be ignored if a macro
  was set to be used on the same element (#16).

2.0.1 (2011-07-23)
------------------

- Fixed issue where global variable definition from macro slots would
  fail (they would instead be local). This also affects error
  reporting from inside slots because this would be recorded
  internally as a global.

- Fixed issue with template cache digest (used for filenames); modules
  are now invalidated whenever any changes are made to the
  distribution set available (packages on ``sys.path``).

- Fixed exception handler to better let exceptions propagate through
  the renderer.

- The disk-based module compiler now mangles template source filenames
  such that the output Python module is valid and at root level (dots
  and hyphens are replaced by an underscore). This fixes issue #17.

- Fixed translations (i18n) on Python 2.5.

2.0 (2011-07-14)
----------------

- Point release.

2.0-rc14 (2011-07-13)
---------------------

Bugfixes:

- The tab character (``\t``) is now parsed correctly when used inside
  tags.

Features:

- The ``RepeatDict`` class now works as a proxy behind a seperate
  dictionary instance.

- Added template constructor option ``keep_body`` which is a flag
  (also available as a class attribute) that controls whether to save
  the template body input in the ``body`` attribute.

  This is disabled by default, unless debug-mode is enabled.

- The page template loader class now accepts an optional ``formats``
  argument which can be used to select an alternative template class.

2.0-rc13 (2011-07-07)
---------------------

Bugfixes:

- The backslash character (followed by optional whitespace and a line
  break) was not correctly interpreted as a continuation for Python
  expressions.

Features:

- The Python expression implementation is now more flexible for
  external subclassing via a new ``parse`` method.

2.0-rc12 (2011-07-04)
---------------------

Bugfixes:

- Initial keyword arguments passed to a template now no longer "leak"
  into the template variable space after a macro call.

- An unexpected end tag is now an unrecoverable error.

Features:

- Improve exception output.

2.0-rc11 (2011-05-26)
---------------------

Bugfixes:

- Fixed issue where variable names that begin with an underscore were
  seemingly allowed, but their use resulted in a compiler error.

Features:

- Template variable names are now allowed to be prefixed with a single
  underscore, but not two or more (reserved for internal use).

  Examples of valid names::

    item
    ITEM
    _item
    camelCase
    underscore_delimited
    help

- Added support for Genshi's comment "drop" syntax::

    <!--! This comment will be dropped -->

  Note the additional exclamation (!) character.

  This fixes addresses issue #10.

2.0-rc10 (2011-05-24)
---------------------

Bugfixes:

- The ``tal:attributes`` statement now correctly operates
  case-insensitive. The attribute name given in the statement will
  replace an existing attribute with the same name, without respect to
  case.

Features:

- Added ``meta:interpolation`` statement to control expression
  interpolation setting.

  Strings that disable the setting: ``"off"`` and ``"false"``.
  Strings that enable the setting: ``"on"`` and ``"true"``.

- Expression interpolation now works inside XML comments.

2.0-rc9 (2011-05-05)
--------------------

Features:

- Better debugging support for string decode and conversion. If a
  naive join fails, each element in the output will now be attempted
  coerced to unicode to try and trigger the failure near to the bad
  string.

2.0-rc8 (2011-04-11)
--------------------

Bugfixes:

- If a macro defines two slots with the same name, a caller will now
  fill both with a single usage.

- If a valid of ``None`` is provided as the translation function
  argument, we now fall back to the class default.

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
