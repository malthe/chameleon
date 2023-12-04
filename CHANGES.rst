Changes
=======

4.3.0 (2023-12-04)
------------------

- Local variable scope is now iterable, completing dict interface.
  (`#390 <https://github.com/malthe/chameleon/pull/390>`_)

- Minor optimizations to rendering logic.

- Implicit translation now provides the translation context, domain,
  and target language to the translation function (if applicable). Previously,
  the target language was provided, but this did not respect a change via
  `i18n:target`.
  (`#369 <https://github.com/malthe/chameleon/issues/369>`_)

- Replace ``pkg_resources`` with newer and faster ``importlib.resources`` and
  ``importlib.metadata``. Just importing ``pkg_resources`` becomes slower and
  slower the more packages are installed.


4.2.0 (2023-09-25)
------------------

- An XML document provided as a string (i.e. decoded) now correctly
  has its content encoding parsed.

- Boolean attributes are now automatically configured for templates in
  non-XML mode, presuming that we're being used to generate HTML.

  This means that the same loading mechanism can be used for both XML-
  and HTML-based templates.


4.1.0 (2023-08-29)
------------------

- Boolean attributes (those configured using the optional
  `boolean_attributes` parameter) now work with $-expression
  interpolation.

  Unlike content and regular attributes, a special check for a falsy
  value is now done for boolean attributes, such that boolean logic
  can be used for interpolation expressions (only a truthy value will
  include the attribute).

  This reverts a change in behavior introduced in 3.8.0.

  Additionally, dynamic attributes now respect the boolean attributes
  configuration as well.

4.0.1 (2023-06-19)
------------------

- Fix format spec applying for f-strings.
  (`#376 <https://github.com/malthe/chameleon/issues/376>`_)

4.0.0 (2023-03-06)
------------------

- Drop support for Python 2.7, 3.5, 3.6.

- Add support for set- and dict comprehensions
  (`#367 <https://github.com/malthe/chameleon/issues/367>`_)

- Remove the following functions resp. modules:

  + ``.utils.text_()``
  + ``.utils.unescape()``
  + ``.compat``


3.10.2 (2022-12-16)
-------------------

- Fix handling of eager compilation with subclassing (e.g. Pyramid integration).

3.10.1 (2022-05-17)
-------------------

- Fix __str__ method of chameleon.exc.TemplateError
  (`#356 <https://github.com/malthe/chameleon/issues/356>`_)

3.10.0 (2022-04-06)
-------------------

- Make scope class dict-like
  (`#305 <https://github.com/malthe/chameleon/issues/305>`_)

- Work in FIPS enabled environments
  (`#345 <https://github.com/malthe/chameleon/issues/345>`_)

- Fix tab handling issue
  (`#350 <https://github.com/malthe/chameleon/issues/350>`_)

3.9.1 (2021-05-14)
------------------

- Avoid various traceback reference cycles.

3.9.0 (2021-02-26)
------------------

- Removed compatibility code for unsupported Python versions

- Dropped support for obsolete Python 3.4

- Fixed namespace handling when redefining a variable in the same ``tal:define``
  (`#237 <https://github.com/malthe/chameleon/issues/237>`_)

- Fixed failure computing a template's digest if ``template.filename`` is None
  (`#254 <https://github.com/malthe/chameleon/issues/254>`_)

3.8.1 (2020-07-06)
------------------

- Added code optimization to reduce sequential appends of static text.

- The `default` symbol in dynamic attributes is now
  symbolic. Previously, it was assigned the string value of the
  default attribute text. A similar change has been made for
  switch/case expressions.

- The built-in `attrs` dictionary of static element attributes now
  correctly works with `tal:define`, etc.

- Fix slice code generation compatibility issue on Python 3.9.

3.8.0 (2020-06-25)
------------------

- Expose default marker as importable symbol
  `chameleon.tales.DEFAULT_MARKER`.

- Removed legacy flag `literal_false`. To get a similar behavior, use
  `boolean_attributes`.

3.7.4 (2020-06-17)
------------------

- Fix brown-bag release.

3.7.3 (2020-06-17)
------------------

- Fix regression introduced in 3.6.2 where the default marker would
  incorrectly change its value between templates, causing issues in
  software which depends on the value being treated as a global
  object.

3.7.2 (2020-05-31)
------------------

- Allow setting a custom value representation function, allowing
  custom formatting of variables during exception formatting.

3.7.1 (2020-05-10)
------------------

- Fix compatibility issue with Python 3.9.


3.7.0 (2020-03-26)
------------------

- Fixed garbage collection issue with variable scope objects (issue #301).

- Fixed issue where setting a global variable would not be available
  locally.

- A `RepeatDict` no longer inherits from `dict` since it does not
  actually provide that interface in a meaningful way.

- Added feature gate `enable_comment_interpolation` which controls
  whether expression interpolation is enabled inside HTML comments
  (default is enabled).

- Added support for Python 3.6+ f-strings (issue #294).

3.6.2 (2019-06-22)
------------------

- Fix SyntaxWarnings in Python 3.8 resulting from comparing literals with 'is'.
  See https://github.com/plone/Products.CMFPlone/issues/2890.

3.6.1 (2019-04-01)
------------------

- Fix limited search expression for illegal double hyphens in HTML
  comments to fix issue #289.

3.6 (2019-02-19)
----------------

- Exclude `RuntimeError` (or `RecursionError` when available) from
  exception wrapping.

- Fix double dollar '$$' escaping such that a double dollar is always
  resolved, either as an interpolation expression, or as an escape
  where it is substituted by a single dollar symbol. This is now
  consistent with Zope's handling of this character.

  Backslash-escaping of dollar-based string interpolation is no longer
  supported. The documentation has been updated to reflect this
  change.

  This fixes issue #283. Note that this reverses some of the changes
  introduced to fix issue #265.

- Drop support for Python 3.3.

3.5 (2018-10-17)
----------------

- Add support for Python 3.8.

- Add support for TAL attributes in an XML declaration tag. This fixes
  issue #269.

- Add support for custom exception handling for the `tal:on-error`
  statement. There is now an option `on_error_handler` available
  as a template configuration (issue #266).

- Fix issue where double '$$' escaping would affect non-interpolation
  expressions such as the bare '$$' (issue #265).

- Fix an issue where backslash dollar escaping would leave the
  backslash character still in place.

3.4 (2018-07-14)
----------------

Bugfixes:

- Fix regression with translations in case of multiple nodes.


3.3 (2018-05-23)
----------------

Bugfixes:

- Reset error token when rendering internal macro calls.

- Fix edge case in exception handler causing recursion.
  [MatthewWilkes]


3.2 (2017-10-06)
----------------

Features:

- Add the automatic variable ``macroname`` that's bound to the name of
  the executing macro. Fixes https://github.com/malthe/chameleon/issues/238

- A tokenizer can now be configured on the template class. This is
  useful in the case where the template file input is modified before
  parsing (for example, where some tags are stripped away) such that
  token positions need to be offset accordingly for error locations to
  be rendered correctly.

- Expression errors now display source marker (previously only
  filename, line and column was shown).

- No longer require Python source files to import modules.
  [mrh1997]

Optimizations:

- Exception tracking now defers metadata allocation to time of error.


3.1 (2017-02-21)
----------------

Features:

- Add option ``restricted_namespace`` which controls whether to
  restrict namespaces to those defined and used by the page template
  language.
  [hansroh]

Bugs:

- Fixed attribute HTML entity escaping issue where an entity such as
  ``&amp;`` would be encoded twice.

Optimizations:

- Simplify exception tracking, reducing bytecode size significantly.

- Avoid checking if a static string is ``None`` during expression
  interpolation.


3.0 (2016-12-07)
----------------

Bugs:

- Fix issue on Python 2 where an exception was not cleared when using
  the pipe operator and was thus accessible through `sys.exc_info()`.

- The "exists" expression no longer leaks error information.

- Escape '$$' into '$' in both content and string expressions.

- Fix use of macro definition inside translation block.

Improvements:

- Allow unquoted attribute values.

- Wrap attribute error thrown when trying to use a non-macro as a
  macro as a `RenderError` to get proper error output.

- Throw a parse error if '--' (double hyphen) appears in an XML
  comment.

- The `i18n:target` attribute now overrides a default
  `target_language` variable and is passed to the translation
  function.

- Include filename in the on-disk cache module name. Previously,
  only the SHA digest in hex representation would be used, making
  it difficult to see where the module came from. This fixes issue
  #132.

- Add support for non-ascii attribute names.
  [sank]

Compatibility:

- Drop support for Python 2.6, 3.1, and 3.2.


2.25 (2016-09-24)
-----------------

- Add explicit support / testing for Python 3.5.

- Add ``\r`` to negative regex matches to the chameleon parser, where ``\n`` is used but ``\r`` was missing.
  Fixes a case, where the tag name was parsed into ``html\r`` instead of ``html``.
  Fixes: https://github.com/malthe/chameleon/issues/219


2.24 (2015-10-28)
-----------------

- Fixed Python 3.5 compatibility.

- Fixed brown bag release.


2.23 (2015-10-26)
-----------------

- Added ``enable_data_attributes`` option that allows using HTML5 data
  attributes as control attributes instead or in addition to XML
  namespace attributes.


2.22 (2015-02-06)
-----------------

- Fix brown bag release.


2.21 (2015-02-06)
-----------------

- Added ``RenderError`` exception which indicates that an error
  occurred during the evaluation of an expression.

- Clean up ``TemplateError`` exception implementation.


2.20 (2015-01-12)
-----------------

- Pass ``search_path`` to template class when loaded using
  ``TemplateLoader`` (or one of the derived classes).
  [faassen]


2.19 (2015-01-06)
-----------------

- Fix logging deprecation.

- Fix environment-based configuration logging error.


2.18 (2014-11-03)
-----------------

- Fix minor compilation error.


2.17 (2014-11-03)
-----------------

- Add support for ``i18n:context``.
  [wiggy]

- Add missing 'parity' repeat property.
  [voxspox]

- Don't modify environment when getting variables from it.
  [fschulze]


2.16 (2014-05-06)
-----------------

- If a repeat expression evaluates to ``None`` then it is now
  equivalent to an empty set.

  This changes a behavior introduced in 2.14.

  This fixes issue #172.

- Remove fossil test dependency on deprecated ``distribute``.

- Add explicit support / testing for Python 3.3 / 3.4.

- Drop explicit support for Python 2.5 (out of maintenance, and no longer
  supported by ``tox`` or ``Travis-CI``).


2.15 (2014-03-11)
-----------------

- Add Support for Python 3.4's ``NameConstant``.
  [brakhane]


2.14 (2013-11-28)
-----------------

- Element repetition using the ``TAL`` namespace no longer includes
  whitespace. This fixes issue #110.

- Use absolute import for ``chameleon.interfaces`` module. This fixes
  issue #161.


2.13-1 (2013-10-24)
-------------------

- Fixing brown bag release.

2.13 (2013-10-21)
-----------------

Bugfixes:

- The template cache mechanism now includes additional configuration
  settings as part of the cache key such as ``strict`` and
  ``trim_attribute_space``.
  [ossmkitty]

- Fix cache issue where sometimes cached templates would not load
  correctly.
  [ossmkitty]

- In debug-mode, correctly remove temporary files when the module
  loader is garbage-collected (on ``__del__``).
  [graffic]

- Fix error message when duplicate i18n:name directives are used in a
  translation.

- Using the three-argument form of ``getattr`` on a
  ``chameleon.tal.RepeatDict`` no longer raises ``KeyError``,
  letting the default provided to ``getattr`` be used. This fixes
  attempting to adapt a ``RepeatDict`` to a Zope interface under
  PyPy.

2.12 (2013-03-26)
-----------------

Changes:

- When a ``tal:case`` condition succeeds, no other case now will.

Bugfixes:

- Implicit translation now correctly extracts and normalizes complete
  sentences, instead of words.
  [witsch]

- The ``default`` symbol in a ``tal:case`` condition now allows the
  element only if no other case succeeds.


2.11 (2012-11-15)
-----------------

Bugfixes:

- An issue was resolved where a METAL statement was combined with a
  ``tal:on-error`` handler.

- Fix minor parser issue with incorrectly formatted processing
  instructions.

- Provide proper error handling for Python inline code blocks.

Features:

- The simple translation function now supports the
  ``translationstring`` interface.

Optimizations:

- Minor optimization which correctly detects when an element has no
  attributes.


2.10 (2012-10-12)
-----------------

Deprecations:

- The ``fast_translate`` function has been deprecated. Instead, the
  default translation function is now always a function that simply
  interpolates the mapping onto the message default or id.

  The motivation is that since version 2.9, the ``context`` argument
  is non-trivial: the ``econtext`` mapping is passed. This breaks an
  expectation on the Zope platform that the ``context`` parameter is
  the HTTP request. Previously, with Chameleon this parameter was
  simply not provided and so that did not cause issues as such.

- The ``ast24`` module has been renamed to ``ast25``. This should help
  clear up any confusion that Chameleon 2.x might be support a Python
  interpreter less than version 2.5 (it does not).

Features:

- The ``ProxyExpr`` expression class (and hence the ``load:``
  expression type) is now a TALES-expression. In practical terms, this
  means that the expression type (which computes a string result using
  the standard ``"${...}"`` interpolation syntax and proxies the
  result through a function) now supports fallback using the pipe
  operator (``"|"``). This fixes issue #128.

- An attempt to interpolate using the empty string as the expression
  (i.e. ``${}``) now does nothing: the string ``${}`` is simply output
  as is.

- Added support for adding, modifying, and removing attributes using a
  dictionary expression in ``tal:attributes`` (analogous to Genshi's
  ``py:attrs`` directive)::

    <div tal:attributes="name value; attrs" />

  In the example above, ``name`` is an identifier, while ``value`` and
  ``attrs`` are Python expressions. However, ``attrs`` must evaluate
  to a Python dictionary object (more concisely, the value must
  implement the dictionary API-methods ``update()`` and ``items()``).

Optimizations:

- In order to cut down on the size of the compiled function objects,
  some conversion and quoting statements have been put into
  functions. In one measurement, the reduction was 35%. The benchmark
  suite does *not* report of an increased render time (actually
  slightly decreased).

Bugfixes:

- An exception is now raised if a trivial string is passed for
  ``metal:fill-slot``. This fixes issue #89.

- An empty string is now never translated. Not really a bug, but it's
  been reported in as an issue (#92) because some translation
  frameworks handle this case incorrectly.

- The template module loader (file cache) now correctly encodes
  generated template source code as UTF-8. This fixes issue #125.

- Fixed issue where a closure might be reused unsafely in nested
  template rendering.

- Fixed markup class ``__repr__`` method. This fixes issue #124.

- Added missing return statement to fix printing the non-abbreviated
  filename in case of an exception.
  [tomo]

2.9.2 (2012-06-06)
------------------

Bugfixes:

- Fixed a PyPy incompatibility.

- Fixed issue #109 which caused testing failures on some platforms.

2.9.1 (2012-06-01)
------------------

Bugfixes:

- Fixed issue #103. The ``tal:on-error`` statement now always adds an
  explicit end-tag to the element, even with a substitution content of
  nothing.

- Fixed issue #113. The ``tal:on-error`` statement now works correctly
  also for dynamic attributes. That is, the fallback tag now includes
  only static attributes.

- Fixed name error which prevented the benchmark from running
  correctly.

Compatibility:

- Fixed deprecation warning on Python 3 for zope interface implements
  declaration. This fixes issue #116.

2.9.0 (2012-05-31)
------------------

Features:

- The translation function now gets the ``econtext`` argument as the
  value for ``context``. Note that historically, this was usually an
  HTTP request which might provide language negotiation data through a
  dictionary interface.
  [alvinyue]

Bugfixes:

- Fixed import alias issue which would lead to a syntax error in
  generated Python code. Fixes issue #114.

2.8.5 (2012-05-02)
------------------

Bugfixes:

- Fixed minor installation issues on Python 2.5 and 3.
  [ppaez]

- Ensure output is unicode even when trivial (an empty string).

2.8.4 (2012-04-18)
------------------

Features:

- In exception output, long filenames are now truncated to 60
  characters of output, preventing line wrap which makes it difficult
  to scan the exception output.

Bugfixes:

- Include filename and location in exception output for exceptions
  raised during compilation.

- If a trivial translation substitution variable is given (i.e. an
  empty string), simply ignore it. This fixes issue #106.

2.8.3 (2012-04-16)
------------------

Features:

- Log template source on debug-level before cooking.

- The `target_language` argument, if given, is now available as a
  variable in templates.

2.8.2 (2012-03-30)
------------------

Features:

- Temporary caches used in debug mode are cleaned up eagerly, rather
  than waiting for process termination.
  [mitchellrj]

Bugfixes:

- The `index`, `start` and `end` methods on the TAL repeat object are
  now callable. This fixes an incompatibility with ZPT.

- The loader now correctly handles absolute paths on Windows.
  [rdale]

2.8.1 (2012-03-29)
------------------

Features:

- The exception formatter now lists errors in 'wrapping order'. This
  means that the innermost, and presumably most relevant exception is
  shown last.

Bugfixes:

- The exception formatter now correctly recognizes nested errors and
  does not rewrap the dynamically generated exception class.

- The exception formatter now correctly sets the ``__module__``
  attribute to that of the original exception class.

2.8.0 (2012-02-29)
------------------

Features:

- Added support for code blocks using the `<?python ... ?>` processing
  instruction syntax.

  The scope is name assignments is up until the nearest macro
  definition, or the template itself if macros are not used.

Bugfixes:

- Fall back to the exception class' ``__new__`` method to safely
  create an exception object that is not implemented in Python.

- The exception formatter now keeps track of already formatted
  exceptions, and ignores them from further output.

2.7.4 (2012-02-27)
------------------

- The error handler now invokes the ``__init__`` method of
  ``BaseException`` instead of the possibly overridden method (which
  may take required arguments). This fixes issue #97.
  [j23d, malthe]

2.7.3 (2012-01-16)
------------------

Bugfixes:

- The trim whitespace option now correctly trims actual whitespace to
  a single character, appearing either to the left or to the right of
  an element prefix or suffix string.

2.7.2 (2012-01-08)
------------------

Features:

- Added option ``trim_attribute_space`` that decides whether attribute
  whitespace is stripped (at most down to a single space). This option
  exists to provide compatibility with the reference
  implementation. Fixes issue #85.

Bugfixes:

- Ignore unhashable builtins when generating a reverse builtin
  map to quickly look up a builtin value.
  [malthe]

- Apply translation mapping even when a translation function is not
  available. This fixes issue #83.
  [malthe]

- Fixed issue #80. The translation domain for a slot is defined by the
  source document, i.e. the template providing the content for a slot
  whether it be the default or provided through ``metal:fill-slot``.
  [jcbrand]

- In certain circumstances, a Unicode non-breaking space character would cause
  a define clause to fail to parse.

2.7.1 (2011-12-29)
------------------

Features:

- Enable expression interpolation in CDATA.

- The page template class now implements dictionary access to macros::

     template[name]

  This is a short-hand for::

     template.macros[name]

Bugfixes:

- An invalid define clause would be silently ignored; we now raise a
  language error exception. This fixes issue #79.

- Fixed regression where ``${...}`` interpolation expressions could
  not span multiple lines. This fixes issue #77.

2.7.0 (2011-12-13)
------------------

Features:

- The ``load:`` expression now derives from the string expression such
  that the ``${...}`` operator can be used for expression
  interpolation.

- The ``load:`` expression now accepts asset specs; these are resolved
  by the ``pkg_resources.resource_filename`` function::

    <package_name>:<path>

  An example from the test suite::

    chameleon:tests/inputs/hello_world.pt

Bugfixes:

- If an attribute name for translation was not a valid Python
  identifier, the compiler would generate invalid code. This has been
  fixed, and the compiler now also throws an exception if an attribute
  specification contains a comma. (Note that the only valid separator
  character is the semicolon, when specifying attributes for
  translation via the ``i18n:translate`` statement). This addresses
  issue #76.

2.6.2 (2011-12-08)
------------------

Bugfixes:

- Fixed issue where ``tal:on-error`` would not respect
  ``tal:omit-tag`` or namespace elements which are omitted by default
  (such as ``<tal:block />``).

- Fixed issue where ``macros`` attribute would not be available on
  file-based templates due to incorrect initialization.

- The ``TryExcept`` and ``TryFinally`` AST nodes are not available on
  Python 3.3. These have been aliased to ``Try``. This fixes issue
  #75.

Features:

- The TAL repeat item now makes a security declaration that grants
  access to unprotected subobjects on the Zope 2 platform::

    __allow_access_to_unprotected_subobjects__ = True

  This is required for legacy compatibility and does not affect other
  environments.

- The template object now has a method ``write(body)`` which
  explicitly decodes and cooks a string input.

- Added configuration option ``loader_class`` which sets the class
  used to create the template loader object.

  The class (essentially a callable) is created at template
  construction time.

2.6.1 (2011-11-30)
------------------

Bugfixes:

- Decode HTML entities in expression interpolation strings. This fixes
  issue #74.

- Allow ``xml`` and ``xmlns`` attributes on TAL, I18N and METAL
  namespace elements. This fixes issue #73.

2.6.0 (2011-11-24)
------------------

Features:

- Added support for implicit translation:

  The ``implicit_i18n_translate`` option enables implicit translation
  of text. The ``implicit_i18n_attributes`` enables implicit
  translation of attributes. The latter must be a set and for an
  attribute to be implicitly translated, its lowercase string value
  must be included in the set.

- Added option ``strict`` (enabled by default) which decides whether
  expressions are required to be valid at compile time. That is, if
  not set, an exception is only raised for an invalid expression at
  evaluation time.

- An expression error now results in an exception only if the
  expression is attempted evaluated during a rendering.

- Added a configuration option ``prepend_relative_search_path`` which
  decides whether the path relative to a file-based template is
  prepended to the load search path. The default is ``True``.

- Added a configuration option ``search_path`` to the file-based
  template class, which adds additional paths to the template load
  instance bound to the ``load:`` expression. The option takes a
  string path or an iterable yielding string paths. The default value
  is the empty set.

Bugfixes:

- Exception instances now support pickle/unpickle.

- An attributes in i18n:attributes no longer needs to match an
  existing or dynamic attribute in order to appear in the
  element. This fixes issue #66.

2.5.3 (2011-10-23)
------------------

Bugfixes:

- Fixed an issue where a nested macro slot definition would fail even
  though there existed a parent macro definition. This fixes issue
  #69.

2.5.2 (2011-10-12)
------------------

Bugfixes:

- Fixed an issue where technically invalid input would result in a
  compiler error.

Features:

- The markup class now inherits from the unicode string type such that
  it's compatible with the string interface.

2.5.1 (2011-09-29)
------------------

Bugfixes:

- The symbol names "convert", "decode" and "translate" are now no
  longer set as read-only *compiler internals*. This fixes issue #65.

- Fixed an issue where a macro extension chain nested two levels (a
  template uses a macro that extends a macro) would lose the middle
  slot definitions if slots were defined nested.

  The compiler now throws an error if a nested slot definition is used
  outside a macro extension context.

2.5.0 (2011-09-23)
------------------

Features:

- An expression type ``structure:`` is now available which wraps the
  expression result as *structure* such that it is not escaped on
  insertion, e.g.::

    <div id="content">
       ${structure: context.body}
    </div>

  This also means that the ``structure`` keyword for ``tal:content``
  and ``tal:replace`` now has an alternative spelling via the
  expression type ``structure:``.

- The string-based template constructor now accepts encoded input.

2.4.6 (2011-09-23)
------------------

Bugfixes:

- The ``tal:on-error`` statement should catch all exceptions.

- Fixed issue that would prevent escaping of interpolation expression
  values appearing in text.

2.4.5 (2011-09-21)
------------------

Bugfixes:

- The ``tal:on-error`` handler should have a ``error`` variable
  defined that has the value of the exception thrown.

- The ``tal:on-error`` statement is a substitution statement and
  should support the "text" and "structure" insertion methods.

2.4.4 (2011-09-15)
------------------

Bugfixes:

- An encoding specified in the XML document preamble is now read and
  used to decode the template input to unicode. This fixes issue #55.

- Encoded expression input on Python 3 is now correctly
  decoded. Previously, the string representation output would be
  included instead of an actually decoded string.

- Expression result conversion steps are now correctly included in
  error handling such that the exception output points to the
  expression location.

2.4.3 (2011-09-13)
------------------

Features:

- When an encoding is provided, pass the 'ignore' flag to avoid
  decoding issues with bad input.

Bugfixes:

- Fixed pypy compatibility issue (introduced in previous release).

2.4.2 (2011-09-13)
------------------

Bugfixes:

- Fixed an issue in the compiler where an internal variable (such as a
  translation default value) would be cached, resulting in variable
  scope corruption (see issue #49).

2.4.1 (2011-09-08)
------------------

Bugfixes:

- Fixed an issue where a default value for an attribute would
  sometimes spill over into another attribute.

- Fixed issue where the use of the ``default`` name in an attribute
  interpolation expression would print the attribute value. This is
  unexpected, because it's an expression, not a static text suitable
  for output. An attribute value of ``default`` now correctly drops
  the attribute.

2.4.0 (2011-08-22)
------------------

Features:

- Added an option ``boolean_attributes`` to evaluate and render a
  provided set of attributes using a boolean logic: if the attribute
  is a true value, the value will be the attribute name, otherwise the
  attribute is dropped.

  In the reference implementation, the following attributes are
  configured as boolean values when the template is rendered in
  HTML-mode::

      "compact", "nowrap", "ismap", "declare", "noshade",
      "checked", "disabled", "readonly", "multiple", "selected",
      "noresize", "defer"

  Note that in Chameleon, these attributes must be manually provided.

Bugfixes:

- The carriage return character (used on Windows platforms) would
  incorrectly be included in Python comments.

  It is now replaced with a line break.

  This fixes issue #44.

2.3.8 (2011-08-19)
------------------

- Fixed import error that affected Python 2.5 only.

2.3.7 (2011-08-19)
------------------

Features:

- Added an option ``literal_false`` that disables the default behavior
  of dropping an attribute for a value of ``False`` (in addition to
  ``None``). This modified behavior is the behavior exhibited in
  reference implementation.

Bugfixes:

- Undo attribute special HTML attribute behavior (see previous
  release).

  This turned out not to be a compatible behavior; rather, boolean
  values should simply be coerced to a string.

  Meanwhile, the reference implementation does support an HTML mode in
  which the special attribute behavior is exhibited.

  We do not currently support this mode.

2.3.6 (2011-08-18)
------------------

Features:

- Certain HTML attribute names now have a special behavior for a
  attribute value of ``True`` (or ``default`` if no default is
  defined). For these attributes, this return value will result in the
  name being printed as the value::

    <input type="input" tal:attributes="checked True" />

  will be rendered as::

    <input type="input" checked="checked" />

  This behavior is compatible with the reference implementation.

2.3.5 (2011-08-18)
------------------

Features:

- Added support for the set operator (``{item, item, ...}``).

Bugfixes:

- If macro is defined on the same element as a translation name, this
  no longer results in a "translation name not allowed outside
  translation" error. This fixes issue #43.

- Attribute fallback to dictionary lookup now works on multiple items
  (e.g. ``d1.d2.d2``). This fixes issue #42.

2.3.4 (2011-08-16)
------------------

Features:

- When inserting content in either attributes or text, a value of
  ``True`` (like ``False`` and ``None``) will result in no
  action.

- Use statically assigned variables for ``"attrs"`` and
  ``"default"``. This change yields a performance improvement of
  15-20%.

- The template loader class now accepts an optional argument
  ``default_extension`` which accepts a filename extension which will
  be appended to the filename if there's not already an extension.

Bugfixes:

- The default symbol is now ``True`` for an attribute if the attribute
  default is not provided. Note that the result is that the attribute
  is dropped. This fixes issue #41.

- Fixed an issue where assignment to a variable ``"type"`` would
  fail. This fixes issue #40.

- Fixed an issue where an (unsuccessful) assignment for a repeat loop
  to a compiler internal name would not result in an error.

- If the translation function returns the identical object, manually
  coerce it to string. This fixes a compatibility issue with
  translation functions which do not convert non-string objects to a
  string value, but simply return them unchanged.

2.3.3 (2011-08-15)
------------------

Features:

- The ``load:`` expression now passes the initial keyword arguments to
  its template loader (e.g. ``auto_reload`` and ``encoding``).

- In the exception output, string variable values are now limited to a
  limited output of characters, single line only.

Bugfixes:

- Fixed horizontal alignment of exception location info
  (i.e. 'String:', 'Filename:' and 'Location:') such that they match
  the template exception formatter.

2.3.2 (2011-08-11)
------------------

Bugfixes:

- Fixed issue where i18n:domain would not be inherited through macros
  and slots. This fixes issue #37.

2.3.1 (2011-08-11)
------------------

Features:

- The ``Builtin`` node type may now be used to represent any Python
  local or global name. This allows expression compilers to refer to
  e.g. ``get`` or ``getitem``, or to explicit require a builtin object
  such as one from the ``extra_builtins`` dictionary.

Bugfixes:

- Builtins which are not explicitly disallowed may now be redefined
  and used as variables (e.g. ``nothing``).

- Fixed compiler issue with circular node annotation loop.

2.3 (2011-08-10)
----------------

Features:

- Added support for the following syntax to disable inline evaluation
  in a comment:

    <!--? comment appears verbatim (no ${...} evaluation) -->

  Note that the initial question mark character (?) will be omitted
  from output.

- The parser now accepts '<' and '>' in attributes. Note that this is
  invalid markup. Previously, the '<' would not be accepted as a valid
  attribute value, but this would result in an 'unexpected end tag'
  error elsewhere. This fixes issue #38.

- The expression compiler now provides methods ``assign_text`` and
  ``assign_value`` such that a template engine might configure this
  value conversion to support e.g. encoded strings.

  Note that currently, the only client for the ``assign_text`` method
  is the string expression type.

- Enable template loader for string-based template classes. Note that
  the ``filename`` keyword argument may be provided on initialization
  to identify the template source by filename. This fixes issue #36.

- Added ``extra_builtins`` option to the page template class. These
  builtins are added to the default builtins dictionary at cook time
  and may be provided at initialization using the ``extra_builtins``
  keyword argument.

Bugfixes:

- If a translation domain is set for a fill slot, use this setting
  instead of the macro template domain.

- The Python expression compiler now correctly decodes HTML entities
  ``'gt'`` and ``'lt'``. This fixes issue #32.

- The string expression compiler now correctly handles encoded text
  (when support for encoded strings is enabled). This fixes issue #35.

- Fixed an issue where setting the ``filename`` attribute on a
  file-based template would not automatically cause an invalidation.

- Exceptions raised by Chameleon can now be copied via
  ``copy.copy``. This fixes issue #36.
  [leorochael]

- If copying the exception fails in the exception handler, simply
  re-raise the original exception and log a warning.

2.2 (2011-07-28)
----------------

Features:

- Added new expression type ``load:`` that allows loading a
  template. Both relative and absolute paths are supported. If the
  path given is relative, then it will be resolved with respect to the
  directory of the template.

- Added support for dynamic evaluation of expressions.

  Note that this is to support legacy applications. It is not
  currently wired into the provided template classes.

- Template classes now have a ``builtins`` attribute which may be used
  to define built-in variables always available in the template
  variable scope.

Incompatibilities:

- The file-based template class no longer accepts a parameter
  ``loader``. This parameter would be used to load a template from a
  relative path, using a ``find(filename)`` method. This was however,
  undocumented, and probably not very useful since we have the
  ``TemplateLoader`` mechanism already.

- The compiled template module now contains an ``initialize`` function
  which takes values that map to the template builtins. The return
  value of this function is a dictionary that contains the render
  functions.

Bugfixes:

- The file-based template class no longer verifies the existence of a
  template file (using ``os.lstat``). This now happens implicitly if
  eager parsing is enabled, or otherwise when first needed (e.g. at
  render time).

  This is classified as a bug fix because the previous behavior was
  probably not what you'd expect, especially if an application
  initializes a lot of templates without needing to render them
  immediately.

2.1.1 (2011-07-28)
------------------

Features:

- Improved exception display. The expression string is now shown in
  the context of the original source (if available) with a marker
  string indicating the location of the expression in the template
  source.

Bugfixes:

- The ``structure`` insertion mode now correctly decodes entities for
  any expression type (including ``string:``). This fixes issue #30.

- Don't show internal variables in the exception formatter variable
  listing.

2.1 (2011-07-25)
----------------

Features:

- Expression interpolation (using the ``${...}`` operator and
  previously also ``$identifier``) now requires braces everywhere
  except inside the ``string:`` expression type.

  This change is motivated by a number of legacy templates in which
  the interpolation format without braces ``$identifier`` appears as
  text.

2.0.2 (2011-07-25)
------------------

Bugfixes:

- Don't use dynamic variable scope for lambda-scoped variables (#27).

- Avoid duplication of exception class and message in traceback.

- Fixed issue where a ``metal:fill-slot`` would be ignored if a macro
  was set to be used on the same element (#16).

2.0.1 (2011-07-23)
------------------

Bugfixes:

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

- The ``RepeatDict`` class now works as a proxy behind a separate
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
