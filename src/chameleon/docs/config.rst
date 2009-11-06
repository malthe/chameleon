Configuration
=============

Environment variables
---------------------

The Chameleon compiler is configurable at startup-time using system environment variables (each default to false):

:term:`CHAMELEON_DEBUG`
     Enable debug-mode when compiling and executing templates. This is highly recommended during development.

:term:`CHAMELEON_CACHE`
     Use a disk-cache to cache template compilations. This substanially decreases startup time for applications with many templates.

:term:`CHAMELEON_EAGER`
     Parse templates on initialization rather than on compilation. This option may be used to verify that templates parse with no errors.

:term:`CHAMELEON_STRICT`
     In strict-mode, filled macro slots must exist in the macro that's being used.

:term:`CHAMELEON_VALIDATE`
     Validate inserted structural content against the XHTML standard.

For all of the above, they may be set to a true or false value (0, 1 and the literals 'true' and 'false' are accepted, case-insensitive).

