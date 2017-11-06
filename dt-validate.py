#!/usr/bin/env python3

import sys
import yaml
import jsonschema
import argparse
import glob

class schema_group():
    def __init__(self):
        self.schemas = dict()
        for filename in glob.iglob("schemas/**/*.yaml", recursive=True):
            self.load_binding_schema(filename)

    def load_binding_schema(self, filename):
        try:
            schema = yaml.load(open(filename).read())
        except yaml.YAMLError as exc:
            print("Error in schema", filename, exc)
            return

        try:
            jsonschema.Draft4Validator.check_schema(schema)
        except jsonschema.SchemaError as exc:
            print("Error(s) validating schema", filename, exc)
            return

        if ("match" in schema):
            schemas[schema.match] = schema
        print("loaded schema", filename)

if __name__ == "__main__":
    sg = schema_group()
    exit(0)

    argparser = argparse.ArgumentParser()
    argparser.add_argument("yamldt", type=str, help="Filename of YAML encoded devicetree input file")
    args = argparser.parse_args()


    schema = yaml.load(open("dt-schema-core.json").read())
    testtree = yaml.load(open(args.yamldt).read())

    errors = jsonschema.Draft4Validator.check_schema(schema)
    if errors:
        for error in errors:
            print(error.path, error.message)
        exit(-1);

    v = jsonschema.Draft4Validator(schema)
    errors = sorted(v.iter_errors(testtree), key=lambda e: e.path)

    if errors:
        for error in errors:
            print(error.path, error.message)
        exit(-1);
