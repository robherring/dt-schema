#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2018 Linaro Ltd.

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dtschema",
    version="0.0.1",
    author="Rob Herring",
    author_email="robh@kernel.org",
    description="DeviceTree validation schema and tools",
    long_description=long_description,
    url="https://github.com/robherring/yaml-bindings",

    packages=['dtschema'],
    package_data={'dtschema': ['meta-schemas/*', 'schemas/*']},

    scripts=['tools/dt-validate', 'tools/dt-doc-validate', 'tools/dt-mk-schema'],

    install_requires=[
        'ruamel.yaml>=0.15.0',
        'jsonschema>2.6.0',
        'rfc3987',
    ],

    dependency_links=[
        'git+https://github.com/Julian/jsonschema.git#egg=jsonschema-2.6.1',
    ],

    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ),
)
