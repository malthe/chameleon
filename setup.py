__version__ = '3.0'

import os

from setuptools import setup, find_packages
from setuptools.command.test import test

here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except:  # doesn't work under tox/pip
    README = ''
    CHANGES = ''

install_requires = []


class Benchmark(test):
    description = "Run benchmarks"
    user_options = []
    test_suite = None

    def initialize_options(self):
        """init options"""
        pass

    def finalize_options(self):
        """finalize options"""

        self.distribution.tests_require = [
            'zope.pagetemplate',
            'zope.component',
            'zope.i18n',
            'zope.testing']

    def run(self):
        test.run(self)
        self.with_project_on_sys_path(self.run_benchmark)

    def run_benchmark(self):
        from chameleon import benchmark
        print("running benchmark...")

        benchmark.start()

setup(
    name="Chameleon",
    version=__version__,
    description="Fast HTML/XML Template Compiler.",
    long_description="\n\n".join((README, CHANGES)),
    classifiers=[
       "Development Status :: 5 - Production/Stable",
       "Intended Audience :: Developers",
       "Programming Language :: Python",
       "Programming Language :: Python :: 2",
       "Programming Language :: Python :: 3",
       "Programming Language :: Python :: 2.7",
       "Programming Language :: Python :: 3.3",
       "Programming Language :: Python :: 3.4",
       "Programming Language :: Python :: 3.5",
       "Programming Language :: Python :: Implementation :: CPython",
       "Programming Language :: Python :: Implementation :: PyPy",
      ],
    author="Malthe Borch",
    author_email="mborch@gmail.com",
    url="https://chameleon.readthedocs.io",
    license='BSD-like (http://repoze.org/license.html)',
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data=True,
    install_requires=install_requires,
    zip_safe=False,
    test_suite="chameleon.tests",
    cmdclass={
        'benchmark': Benchmark,
        }
    )

