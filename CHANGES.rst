Changes
=======

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
