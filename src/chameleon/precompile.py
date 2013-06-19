"""Script to pre-compile chameleon templates to the cache.

This script is useful if the time to compile chameleon templates is
unacceptably long. It finds and compiles all templates within a directory,
saving the result in the cache configured via the CHAMELEON_CACHE environment
variable.
"""

import os
import sys
import logging
import optparse

from chameleon.config import CACHE_DIRECTORY
from chameleon.zpt.template import PageTemplateFile

def compile_one(fullpath, template_factory=PageTemplateFile):
    assert CACHE_DIRECTORY is not None
    template = template_factory(fullpath)
    template.cook_check()

def walk_dir(
        directory,
        extensions=frozenset(['.pt']),
        template_factory=PageTemplateFile,
        fail_fast=False):
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            if filename.startswith('.'):
                continue
            _, ext = os.path.splitext(filename)
            if ext not in extensions:
                continue
            fullpath = os.path.join(dirpath, filename)
            try:
                compile_one(fullpath, template_factory=template_factory)
            except:
                if fail_fast:
                    raise
                yield dict(
                    path=fullpath,
                    success=False)
                logging.warn('Failed to compile: %s' % fullpath)
                continue
            logging.debug('Compiled: %s' % fullpath)
            yield dict(
                path=fullpath,
                success=True)

def compile(argv=sys.argv):
    parser = optparse.OptionParser(usage="""usage: %prog [options]

Compile chameleon templates, saving the results in the chameleon cache.

The CACHE_DIRECTORY environment variable MUST be set to the directory where the
templates will be stored.

By default the exit code of this script will be 0 if one template was found and
compiled.
""")
    parser.add_option(
            "--fail-fast",
            dest="fail_fast",
            default=False,
            action="store_true",
            help="Exit with non-zero exit code on the first "
                 "template which fails compillation.")
    parser.add_option(
            "--dir",
            dest="dir",
            help="The directory to search for tempaltes. "
                 "Will be recursively searched")
    parser.add_option(
            "--ext",
            dest="exts",
            action="append",
            help="The file extensions to search for, "
                 "can be specified more than once."
                 "The default is to look only for the .pt extension.")
    parser.add_option(
            "--loglevel",
            dest="loglevel",
            help="set the loglevel, see the logging module for possible values",
            default='INFO')
    options, args = parser.parse_args(argv)
    loglevel = getattr(logging, options.loglevel)
    logging.basicConfig(level=loglevel)
    if CACHE_DIRECTORY is None:
        logging.error('The CHAMELEON_CACHE environment variable must be specified')
        sys.exit(1)
    if len(args) > 1:
        msg = ' '.join(args[1:])
        logging.error('This command takes only keyword arguments, got: %s' % msg)
        sys.exit(1)
    exts = options.exts
    if not exts:
        exts = ['.pt']
    exts = set(exts)
    success = total = 0
    for f in walk_dir(options.dir, extensions=exts, fail_fast=options.fail_fast):
        total += 1
        if f['success']:
            success += 1
    logging.info('Compiled %s out of %s found templates' % (success, total))
    if not success:
        logging.error("No templates successfully compiled out of %s found" % total)
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    compile()
