#!/usr/bin/env python # -- coding: utf-8 --

from setuptools import setup, find_packages
import sys

version = '1.0.5'

install_requires = [
    'setuptools',
    'sourcecodegen>=0.6.11',
    ]

if sys.version_info[:3] < (2,5,0):
    install_requires.append('elementtree')

setup(name="Chameleon",
      version=version,
      description="XML-based template compiler.",
      long_description=open("README.rst").read() + open("CHANGES.rst").read(),
      classifiers=[
        "Programming Language :: Python",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Text Processing :: Markup :: XML",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='',
      author='Malthe Borch and the Repoze Community',
      author_email="repoze-dev@lists.repoze.org",
      url="http://chameleon.repoze.org",
      license='BSD',
      namespace_packages=['chameleon'],
      packages = find_packages('src'),
      package_dir = {'':'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      tests_require=install_requires + [
          'zope.interface==3.5.2',
          'zope.component==3.7.1',
          'zope.i18n==3.7.1'
          ],
      test_suite="chameleon.tests",
      )
