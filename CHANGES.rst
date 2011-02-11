Changes
=======

1.3.0-rc1 (released 2011-02-11)
-------------------------------

- Fix issue where object identifiers (``id``) would be negative (on
  some platforms).
  [malthe]

- Fix debug mode with disk caching off where temporary caches were created in
  the wrong place (i.e. alongside the file rather than in a temporary
  directory).
  [jinty]

- Fixed issue with eager loading and template initialization.
  [aikom]

- Fix mishandling of XML declaration. (LP#360296)
  [rpatterson]

- Fix an AttributeError for objects which don't have a '__class__'
  attribute.
  [rpatterson]

- When doing metal:fill-slot, any tal:repeat in the metal:define-slot
  element should be replaced/ignored.  (LP#665748)
  [rpatterson]

- Handle some broken TAL syntax with attributes/define with no values
  given.
  [rossp]

1.2.13 (released 2010-09-23)
----------------------------

- Fixed issue where a repeat variable's entry in the ``repeat`` symbol
  would not get carried over with a macro slot (LP #644712; reported
  by Joshua LaPlace).

- Added support for ``attrs`` (read-only dictionary which contains
  static attributes).

- Fixed issue where the temporary template cache which is set up to
  aid debugging would not get purged automatically.

1.2.12 (released 2010-09-09)
----------------------------

- Parser is now able to parse documents which contain non-structured
  fragments.

- Compiler now reports an error if an expression type is unknown.

- Edge-case issue where an expression result was actually not a
  dynamic value, but a static string (e.g. ``string: Hello``).

1.2.11 (released 2010-09-07)
----------------------------

- Avoid escaping already computed content from named regions inside a
  translation block.

- Always generate dynamic message ids dynamically when unnamed
  elements are present.

- Fixed an issue where the presence of an unnamed elements inside an
  anonymous translation block would result in an error when
  translation failed.

- Put a lock around compilation. This should guarantee stability (some
  reports suggest that there's code in the compilation loop which is
  not thread-safe) without a drop in performance (GIL is there, in
  spite all).

1.2.10 (released 2010-07-15)
----------------------------

- Fixed an issue where it was not possible to extend a macro by
  providing the template instance.

1.2.9 (released 2010-07-09)
---------------------------

- When using unnamed elements in a translation clause, use the element
  visit function to generate output, rather than static serialization.

- Fix handling of i18n:attributes in Babel template extractor.


1.2.8 (released 2010-07-08)
---------------------------

- Make the implementation used for XIncludes minimally hookable by
  causing ``chameleon.core.template.TemplateFile`` to use symbolic
  ``self.xincludes_class`` constructor instead of the
  ``chameleon.core.template.XIncludes`` class directly.


1.2.7 (released 2010-07-08)
---------------------------

- Update Babel extractor for python to check source file encoding. This
  fixes problems with non-ASCII strings.


1.2.6 (released 2010-06-21)
---------------------------

- Resolve real path before checking the XInclude registry. This fixes
  cache misses when using relative paths.


1.2.5 (released 2010-06-21)
---------------------------

- Use a blacklist to filter python builtins available in expressions. This
  fixes the disappearance of many common builtins in the previous release.


1.2.4 (released 2010-06-21)
---------------------------

- Fix in Babel python i18n extractor: correct  handling of messages with a
  newline before the start of a parameter.

- Drop list of rarely used builtins from scope (such as ``help``);
  meanwhile, the builtins that are made available won't be replaced by
  arguments passed into the template.

  We can change this behavior by adding names to the list of
  *transient symbols*; however, this is expensive. The right place to
  do it would be the code stream's dictionary of required symbols, but
  it's currently a cumbersome solution.

  Consider this a temporary fix.

- Fixed issue where an interpolation escape would indeed escape
  interpolation, but also display in the output. [sklein]

- Translate attributes that are messages.

1.2.3 (released 2010-04-19)
---------------------------

- Added parameter ``debug`` to template constructor to enable debug
  mode. The default value is taken from the ``CHAMELEON_DEBUG``
  environment value and defaults to ``False``.

  The use of debug mode is recommended during development.

- Improved exception output in debug-mode; for nested usage, sections
  now carry the correct filename.

- Fixed an issue where an incorrect expression annotation would be
  shown, or none at all.

- When in debug-mode, take steps to ensure traceback is not swallowed
  in properties by explicit invocation.

1.2.2 (released 2010-04-17)
---------------------------

- Fixed regression where objects that are not strings or numbers would
  not output due to a recent change in policy that subjected such
  objects to the translation machinery. However, the default
  translation function had a bug that instead returned ``None``.

  The new behavior is that such objects are coerced to unicode by
  default.

  Note that if ``zope.i18n`` is available, an alternative translation
  function is used; this function, however, has the correct behavior
  already.

- Fixed issue where nested translations would drop named blocks due to
  a name clash.

1.2.1 (released 2010-04-07)
---------------------------

- Fixed issue where decorators used internally by the compiler would
  be silently dropped during compilation on Python 2.4. This fix
  solves an issue with match templates not being processed.

- Objects which are not strings or numbers, and which do not provide
  an ``__html__`` method, are now considered i18n messages. This means
  that they are automatically translated (using interpolation or
  tag-based text insertion or replacement).

- Fixed issue where ``translate`` parameter would not be applicable on
  file-based templates.

- Add Babel message extractors for Python, ZPT and Genshi files.

- Correctly handle translations where a msgid has an empty translation.

1.2.0 (released 2010-03-29)
---------------------------

- Fixed issue where nested translations would fail.

- Added support for passing in a translation function to the template
  constructor.

- Fixed issue where translation name mappings would conflict with
  template function definitions.

- Fixed symbol lookup issue with list comprehensions and lambda
  expressions.

- Fixed issue with interpolation flag and CDATA; the effect of this
  flag is now recursive, which indirectly means that CDATA elements
  will be affected by a setting on a parent tag.

- XML namespace fixes.

- Template instances may now be used as macros; this will use the
  template in its entirety, including any XML declarations. This
  addresses issue #139.

- Integrated Genshi implementation.

- Allow expression interpolation on any tag which is not part of the
  Chameleon or ZPT namespaces (e.g. TAL, METAL, I18N or META).

- Improve XML parsing error handling.

1.1.2 (released 2010-02-24)
---------------------------

- Avoid printing document header strings (XML header and DOCTYPE)
  twice; this would previously happen if a template would define these
  and use a macro on the top level which also provided them.

- The repeat variable attributes (``odd``, ``even`` etc.) are now
  *callable strings*, e.g. legacy users may still call these attributes,
  but it is no longer required.

- The ``odd`` and ``even`` attributes now return the English strings
  ``"odd"`` and ``"even"`` in place of ``True`` and the empty string
  ``""`` instead of ``False``.

1.1.1 (released 2010-01-26)
---------------------------

- Python 2.5 compatibility fixes (symptom: ``TypeError: default
  __new__ takes no parameters`` with the statement generating the
  error something like ``ast.Name("econtext", ast.Load())``).

1.1 (released 2010-01-26)
-------------------------

- Made all tests compatible with Python 2.4.

- Use the 2.5 AST for code transformation for compatibility with
  Google App Engine. The AST utilities required were copied from
  Genshi (license document included).

1.0.8 (released 2010-01-12)
---------------------------

- Use RPL license (http://repoze.org/license.html); include RPL and
  copyright notice in software.

1.0.7 (released 2010-01-07)
---------------------------

- Fixed encoding issue of translated attributes. [kobold]

- Fixed translation issue, that would prevent translation of tag
  contents with both named and unnamed subtags. [kobold]

- Fixed issue where messages could contain a double space. [kobold]

1.0.6 (released 2009-12-14)
---------------------------

- Fixed white space issue.

- Fixed character encoding issue.

- Fixed issue where macro extension would fail.

1.0.5 (released 2009-12-08)
---------------------------

- Fixed issue where the translation compiler would break on messages
  that contained the formatting character '%'.

- Fixed white space issue.

1.0.4 (released 2009-11-15)
---------------------------

- Fixed issue where the file-based template constructor did not accept
  the ``encoding`` parameter.

- Use more caution when falling back to dictionary lookup.

1.0.3 (released 2009-11-12)
---------------------------

- Fixed issue where traceback would contain erroneous debugging
  information. The source code is now taken directly from the
  traceback object.

- Include Python expression in syntax error exception message.

1.0.2 (released 2009-11-10)
---------------------------

- Really fixed ZCA import fallbacks.

1.0.1 (released 2009-11-04)
---------------------------

- Fixed ZCA import fallbacks.

1.0 (released 2009-11-01)
-------------------------

Features:

- HTML5 doctype is now supported.
