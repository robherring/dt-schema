# Prototype tooling for devicetree validation using YAML and jsonschema

This repository contains test code for devicetree schema validation using the
[json-schema](http://json-schema.org/documentation.html) vocabulary. Schema
files are written in YAML (a superset of JSON), and operate on the YAML
encoding of Devicetree data. Devicetree data must be transcoded from DTS to
YAML before being used by this tool

## Data Model

To understand how validation works, it is important to understand how schema data is organized and used.
If you're reading this, I assume you're already familiar with Devicetree and the .dts file format.

In this repository you will find three kinds of files; *YAML Devicetrees*, *Schemas* and *Meta-Schemas*.

### *YAML Devicetrees*

Found under `./test`

*YAML Devicetrees* files are regular .dts files transcoded into a YAML
representation.
There is no special information in these files.
They are used as test cases against the validation tooling.

### *Devicetree Schemas*

Found under `./schemas`

*Devicetree Schemas* describe the format of devicetree data.
The raw Devicetree file format is very open ended and doesn't restrict how
data is encoded.
Hence, it is easy to make mistakes when writing a Devicetree.
Schema files impose constraints on what data can be put into a devicetree.
As the foundation, a single core schema describes all the common property types
that every devicetree node must match.
e.g. In every node the 'compatible' property must be an array of strings.
However, most devicetree data is heterogeneous as each device binding requires
a different set of data, therefore multiple schema files are used to capture the
data format of an entire devicetree.

When validating, the tool will load all the schema files it can find and then
iterate over all the nodes of the devicetree.
For each node, the tool will determine which schema(s) are applicable and make sure
the node data matches the schema constraints.
Nodes failing a schema test will emit an error.
Nodes that don't match any schema will emit a warning.

As a developer, you would write a devicetree schema file for each new
device binding that you create and add it to the `./schemas` directory.

Schema files also have the dual purpose of documenting a binding.
When you define a new binding, you only have to create one file that contains
both the machine-verifiable data format and the documentation.
Documentation generation tools are being written to extract documentation
from a schema file and emit a format that can be included in the devicetree
specification documents.

Devicetree Schema files are normal YAML files using the jsonschema vocabulary.

### *Devicetree Meta-Schemas*

Found in `./meta-schemas`

*Devicetree Meta-Schemas* describe the data format of Devicetree Schema files.
The Meta-schemas make sure all the binding schemas are in the correct format
and the tool will emit an error is the format is incorrect.

As a developer you normally will not need to write metaschema files.

Devicetree Meta-Schema files are normal YAML files using the jsonschema vocabulary.

## Usage
The tool in this repo can be run by simply executing the dt-validate.py script
at the top level. It requires Python 3 to be installed, as well as the
jsonschema and pyyaml libraries.

Please note: this is prototype code and is in no way officially supported or
fit for use.

## Dependencies
This code depends on Python 3 with the yaml and jsonschema libraries

On Debian, the dependencies can be installed with:

```
apt-get install python3 python-yaml
```

### jsonschema Draft6
This code depends on the 'draft6' branch of the
[Python jsonschema](https://github.com/Julian/jsonschema/tree/draft6)
library.
The draft6 branch is incomplete and unreleased, so you will need to get
a local copy instead of using a packaged version.
For convenience a [fork of the draft6 branch](https://github.com/devicetree-org/jsonschema/tree/draft6)
is maintained in the devicetree.org GitHub page,
and this repo includes it as a git submodule.

To fetch the submodule use the following commands:

```
git submodule init
git submodule update
cd jsonschema-draft6 && python3 setup.py && cd ..
```
