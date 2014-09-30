#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


from platform import python_version_tuple
import re


LICENSE = open("LICENSE").read()


# strip links from the descripton on the PyPI
LONG_DESCRIPTION = open("README.rst").read().replace("`_", "`")
# strip build Status from the PyPI package
if python_version_tuple()[:2] >= ('2', '7'):
    LONG_DESCRIPTION = re.sub("^Build Status\n(.*\n){7}", "",
                              LONG_DESCRIPTION, flags=re.M)


setup(name='optirx',
      version='0.2',
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
                     "Programming Language :: Python :: 3.2",
                     "Programming Language :: Python :: 3.3",
                     "Programming Language :: Python :: 3.4",
                     "Topic :: Software Development :: Libraries" ],
      py_modules = ['optirx'])
