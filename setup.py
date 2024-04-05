__version__ = '4.5.3'

import os

from setuptools import find_packages
from setuptools import setup
from setuptools.command.test import test


here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except BaseException:  # doesn't work under tox/pip
    README = ''
    CHANGES = ''

install_requires = ['importlib-metadata;python_version<"3.10"']


class Benchmark(test):
    description = "Run benchmarks"

    def finalize_options(self):
        self.distribution.tests_require = [
            'zope.pagetemplate',
            'zope.component',
            'zope.i18n',
            'zope.testing']

        test.finalize_options(self)

    def run_tests(self):
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
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    author="Malthe Borch",
    author_email="mborch@gmail.com",
    url="https://chameleon.readthedocs.io",
    project_urls={
        'Documentation': 'https://chameleon.readthedocs.io',
        'Issue Tracker': 'https://github.com/malthe/chameleon/issues',
        'Sources': 'https://github.com/malthe/chameleon',
    },
    license='BSD-like (http://repoze.org/license.html)',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    package_data={
        'chameleon': [
            'py.typed',
        ],
    },
    python_requires='>=3.9',
    install_requires=install_requires,
    extras_require={
        'docs': {
            'Sphinx',
            'sphinx_rtd_theme',
        },
    },
    zip_safe=False,
    cmdclass={
        'benchmark': Benchmark,
    }
)
