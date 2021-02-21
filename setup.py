#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of command_runner package


import codecs
import os
import shutil

import pkg_resources
import setuptools


def get_metadata(package_file):
    """
    Read metadata from package file
    """

    def _read(_package_file):
        here = os.path.abspath(os.path.dirname(__file__))
        with codecs.open(os.path.join(here, _package_file), 'r') as fp:
            return fp.read()

    _metadata = {}

    for line in _read(package_file).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            _metadata['version'] = line.split(delim)[1]
        if line.startswith('__description__'):
            delim = '"' if '"' in line else "'"
            _metadata['description'] = line.split(delim)[1]
    return _metadata


def parse_requirements(filename):
    """
    There is a parse_requirements function in pip but it keeps changing import path
    Let's build a simple one
    """
    try:
        with open(filename, 'r') as requirements_txt:
            install_requires = [
                str(requirement)
                for requirement
                in pkg_resources.parse_requirements(requirements_txt)
            ]
        return install_requires
    except OSError:
        print('WARNING: No requirements.txt file found as "{}". Please check path or create an empty one'
              .format(filename))


def get_long_description(filename):
    with open(filename, 'r', encoding='utf-8') as readme_file:
        _long_description = readme_file.read()
    return _long_description

with open('README.md', 'r', encoding='utf-8') as readme_file:
    long_description = readme_file.read()


PACKAGE_NAME = 'command_runner'
package_path = os.path.abspath(PACKAGE_NAME)
package_file = os.path.join(package_path, '__init__.py')
metadata = get_metadata(package_file)
#requirements = parse_requirements(os.path.join(package_path, 'requirements.txt'))

setuptools.setup(
    name='command_runner',
    # We may use find_packages in order to not specify each package manually
    # packages = ['command_runner'],
    packages=setuptools.find_packages(),
    version=metadata['version'],
    # install_requires=requirements,
    classifiers=[
        # command_runner is mature
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "Topic :: System",
        "Topic :: System :: Operating System",
        "Topic :: System :: Shells",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Operating System :: POSIX :: Linux",
        "Operating System :: POSIX :: BSD :: FreeBSD",
        "Operating System :: POSIX :: BSD :: NetBSD",
        "Operating System :: POSIX :: BSD :: OpenBSD",
        "Operating System :: Microsoft",
        "Operating System :: Microsoft :: Windows",
        "License :: OSI Approved :: BSD License",
    ],
    description='Platform agnostic command and shell execution tool, also allows UAC/sudo privilege elevation',
    author='NetInvent - Orsiris de Jong',
    author_email='contact@netinvent.fr',
    url='https://github.com/netinvent/command_runner',
    keywords=['shell', 'execution', 'subprocess', 'check_output', 'wrapper', 'uac', 'sudo', 'elevate', 'privilege'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires='>=2.7',
)
