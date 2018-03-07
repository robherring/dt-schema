# Prototype tooling for devicetree validation using YAML and jsonschema

This repository contains test code for devicetree schema validation using the
[json-schema](http://json-schema.org/documentation.html) vocabulary. Schema
files are written in YAML (a superset of JSON), and operate on the YAML
encoding of Devicetree data. Devicetree data must be transcoded from DTS to
YAML before being used by this tool

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
