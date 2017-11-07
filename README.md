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
