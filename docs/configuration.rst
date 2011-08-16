Configuration
=============

Most settings can be provided as keyword-arguments to the template
constructor classes.

There are certain settings which are required at environment
level. Acceptable values are ``"0"``, ``"1"``, or the literals
``"true"`` or ``"false"`` (case-insensitive).

General usage
-------------

The following settings are useful in general.

``CHAMELEON_EAGER``
   Parse and compile templates on instantiation.

``CHAMELEON_CACHE``

   When set to a file system path, the template compiler will write
   its output to files in this directory and use it as a cache.

   This not only enables you to see the compiler output, but also
   speeds up startup.

``CHAMELEON_RELOAD``
   This setting controls the default value of the ``auto_reload``
   parameter.

Development
-----------

The following settings are mostly useful during development or
debugging of the library itself.

``CHAMELEON_DEBUG``

   Enables a set of debugging settings which make it easier to
   discover and research issues with the engine itself.

   This implicitly enables auto-reload for any template.

