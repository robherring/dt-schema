#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2018 Linaro Ltd.

import setuptools
import glob
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

data_files = []
os.chdir('dtschema')
for filename in glob.iglob("schemas/**/*.yaml", recursive=True):
    data_files.append(filename)
for filename in glob.iglob("meta-schemas/**/*.yaml", recursive=True):
    data_files.append(filename)
os.chdir('..')

setuptools.setup(
    name="dtschema",
    version="0.0.1",
    author="Rob Herring",
    author_email="robh@kernel.org",
    description="DeviceTree validation schema and tools",
    long_description=long_description,
    url="https://github.com/robherring/yaml-bindings",

    packages=['dtschema'],
    package_data={'dtschema': data_files},

    scripts=[
        'tools/dt-validate',
        'tools/dt-doc-validate',
        'tools/dt-mk-schema',
        'tools/dt-extract-example'
    ],

    python_requires='>=3.5',

    install_requires=[
        'ruamel.yaml>0.15.69',
        'jsonschema>=3.0.1',
        'rfc3987',
    ],

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
