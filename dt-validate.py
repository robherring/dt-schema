#!/usr/bin/env python3

import signal

def sigint_handler(signum, frame):
    sys.exit(-2)

signal.signal(signal.SIGINT, sigint_handler)

import sys
import os
basedir = os.path.dirname(__file__)
import ruamel.yaml
sys.path.insert(0, os.path.join(basedir, "jsonschema-draft6"))
import jsonschema
import argparse
import glob
import dtschema

yaml = ruamel.yaml.YAML()

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

def get_select_schema(schema):
    '''Get a schema to be used in select tests.

    If the provided schema has a 'select' property, then use that as the select schema.
    If it has a compatible property, then create a select schema from that.
    If it has neither, then return a match-nothing schema
    '''
    compatible_list = [ ]
    if "select" in schema.keys():
        return schema["select"]

    if not 'properties' in schema.keys():
        return {"not": {}}

    if not 'compatible' in schema['properties'].keys():
        return {"not": {}}

    for l in item_generator(schema['properties']['compatible'], 'enum'):
        compatible_list.extend(l)

    for l in item_generator(schema['properties']['compatible'], 'const'):
        compatible_list.extend(l)

    compatible_list = list(set(compatible_list))

    return { 'required': ['compatible'],
             'properties': {'compatible': {'contains': {'enum': compatible_list}}}}

class schema_group():
    def __init__(self):
        self.schemas = list()
        for filename in glob.iglob("schemas/**/*.yaml", recursive=True):
            self.load_binding_schema(filename)

    def load_binding_schema(self, filename):
        try:
            schema = dtschema.load_schema(filename)
        except ruamel.yaml.error.YAMLError as exc:
            print(filename + ": ignoring, error parsing file")
            return

        # Check that the validation schema is valid
        try:
            dtschema.DTValidator.check_schema(schema)
        except jsonschema.SchemaError as exc:
            print(filename + ": ignoring, error in schema '%s'" % exc.path[-1])
            #print(exc.message)
            return

        # $validator and $select_validator are special properties that cache the
        # validator objects so the object doesn't need to be recreated on every node.
        schema["$validator"] = dtschema.DTValidator(schema)
        schema["$select_validator"] = jsonschema.Draft6Validator(get_select_schema(schema))
        self.schemas.append(schema)

        schema["$filename"] = filename
        print(filename + ": loaded")

    def check_node(self, tree, node, filename, path):
        node_matched = False
        for schema in self.schemas:
            if schema['$select_validator'].is_valid(node):
                node_matched = True
                errors = sorted(schema['$validator'].iter_errors(node), key=lambda e: e.linecol)
                for error in errors:
                    print(dtschema.format_error(filename, error))
        if not node_matched:
            if 'compatible' in node:
                print("%s:%i:%i: %s failed to match any schema with compatible(s) %s" % (filename, node.lc.line, node.lc.col, path, node["compatible"]))
            else:
                print("%s: node %s failed to match any schema" % (filename, path))

    def check_subtree(self, tree, subtree, filename, path='/'):
        self.check_node(tree, subtree, filename, path)
        for name,value in subtree.items():
            if type(value) == ruamel.yaml.comments.CommentedMap:
                self.check_subtree(tree, value, filename, path='/'.join([path,name]))

    def check_trees(self, filename, dt):
        """Check the given DT against all schemas"""
        for subtree in dt:
            self.check_subtree(subtree, subtree, filename)

if __name__ == "__main__":
    sg = schema_group()

    ap = argparse.ArgumentParser()
    ap.add_argument("yamldt", type=str,
                    help="Filename of YAML encoded devicetree input file")
    args = ap.parse_args()


    if os.path.isdir(args.yamldt):
        for filename in glob.iglob(args.yamldt + "/**/*.yaml", recursive=True):
            testtree = dtschema.load(open(filename).read())
            sg.check_trees(filename, testtree)
    else:
        testtree = dtschema.load(open(args.yamldt).read())
        sg.check_trees(args.yamldt, testtree)

