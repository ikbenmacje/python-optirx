#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


from platform import python_version_tuple


LICENSE = open("LICENSE").read()


# strip links from the descripton on the PyPI
LONG_DESCRIPTION = open("README.rst").read().replace("`_", "`")


setup(name='optirx',
      version='0.1',
      description='A pure Python library to receive motion capture data from OptiTrack Streaming Engine',
      long_description=LONG_DESCRIPTION,
      author='Sergey Astanin',
      author_email='s.astanin@gmail.com',
      url='https://bitbucket.org/astanin/python-optirx',
      license=LICENSE,
      classifiers= [ "Development Status :: 4 - Beta",
                     "License :: OSI Approved :: MIT License",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python :: 2.7",
                     "Topic :: Software Development :: Libraries" ],
      py_modules = ['optirx'])
