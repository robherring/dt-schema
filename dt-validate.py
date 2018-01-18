#!/usr/bin/env python3

import sys
import yaml
import jsonschema
import argparse
import glob

def item_generator(json_input, lookup_key):
    if isinstance(json_input, dict):
        for k, v in json_input.items():
            if k == lookup_key:
                if isinstance(v, str):
                    yield [v]
                else:
                    yield v
            else:
                for child_val in item_generator(v, lookup_key):
                    yield child_val
    elif isinstance(json_input, list):
        for item in json_input:
            for item_val in item_generator(item, lookup_key):
                yield item_val

def compatible_select(schema):
    compatible_list = [ ]
    if not 'properties' in schema.keys():
        return None

    if 'compatible' in schema['properties'].keys():
        for l in item_generator(schema['properties']['compatible'], 'enum'):
            compatible_list.extend(l)

        for l in item_generator(schema['properties']['compatible'], 'const'):
            compatible_list.extend(l)

        compatible_list = list(set(compatible_list))

        return { 'required' : ['compatible'], 'properties': {'compatible': {'contains': {'enum': compatible_list}}}}

    return None


class schema_group():
    def __init__(self):
        self.schemas = list()
        for filename in glob.iglob("schemas/**/*.yaml", recursive=True):
            self.load_binding_schema(filename)

    def load_binding_schema(self, filename):
        try:
            schema = yaml.load(open(filename).read())
        except yaml.YAMLError as exc:
            print("Error in schema", filename, exc)
            return

        # Check that the validation schema is valid
        try:
            jsonschema.Draft4Validator.check_schema(schema)
        except jsonschema.SchemaError as exc:
            print("Error(s) validating schema", filename, exc)
            return

        # Check that the selection schema is valid. The selection
        # schema determines when a binding should get applied
        resolver = jsonschema.RefResolver.from_schema(schema)
        validator = jsonschema.Draft6Validator(schema, resolver=resolver)
        if "select" in schema.keys():
            try:
                validator.check_schema(schema)
            except jsonschema.SchemaError as exc:
                print("Error(s) validating schema", filename, exc)
                return

        schema["filename"] = filename

        select = compatible_select(schema)
        if select is not None:
            print("no select")
            schema["select"] = select

        self.schemas.append(schema)
        print("loaded schema", filename)

    def check_node(self, dt, node, path):
        #print("checking node", path, "against a schemas")
        for schema in self.schemas:
            if "select" in schema.keys():
                resolver = jsonschema.RefResolver.from_schema(schema)
                v = jsonschema.Draft6Validator(schema["select"], resolver=resolver)
                if v.is_valid(node):
                    print("node", path, "matches", schema["filename"])
                    v2 = jsonschema.Draft6Validator(schema, resolver=resolver)
                    errors = sorted(v2.iter_errors(node), key=lambda e: e.path)
                    if (errors):
                        for error in errors:
                            print(error.path, error.message)

    def check_subtree(self, dt, subtree, path="/"):
        self.check_node(dt, subtree, path)
        for name,value in subtree.items():
            if type(value) == dict:
                self.check_subtree(dt, value, '/'.join([path,name]))

    def check_trees(self, dt):
        """Check the given DT against all schemas"""
        for subtree in dt:
            self.check_subtree(dt, subtree)

if __name__ == "__main__":
    sg = schema_group()

    ap = argparse.ArgumentParser()
    ap.add_argument("yamldt", type=str,
                    help="Filename of YAML encoded devicetree input file")
    args = ap.parse_args()


    testtree = yaml.load(open(args.yamldt).read())
    sg.check_trees(testtree)
    exit(0)

    schema = yaml.load(open("dt-schema-core.json").read())

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
