# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2018 Linaro Ltd.
# Copyright 2018 Arm Ltd.
# Python library for Devicetree schema validation
import sys
import os
import glob
import ruamel.yaml
import re

from ruamel.yaml.comments import CommentedMap

import jsonschema
import pkgutil

schema_base_url = "http://devicetree.org/"

def scalar_constructor(loader, node):
    return loader.construct_scalar(node)
def sequence_constructor(loader, node):
    return loader.construct_sequence(node)
ruamel.yaml.RoundTripLoader.add_constructor(u'!u8', sequence_constructor)
ruamel.yaml.RoundTripLoader.add_constructor(u'!u16', sequence_constructor)
ruamel.yaml.RoundTripLoader.add_constructor(u'!u32', sequence_constructor)
ruamel.yaml.RoundTripLoader.add_constructor(u'!u64', sequence_constructor)
ruamel.yaml.RoundTripLoader.add_constructor(u'!phandle', scalar_constructor)
ruamel.yaml.RoundTripLoader.add_constructor(u'!path', scalar_constructor)

def path_to_obj(tree, path):
    for pc in path:
        tree = tree[pc]
    return tree

def get_line_col(tree, path, obj=None):
    if isinstance(obj, ruamel.yaml.comments.CommentedBase):
        return obj.lc.line, obj.lc.col
    obj = path_to_obj(tree, path)
    if isinstance(obj, ruamel.yaml.comments.CommentedBase):
        return obj.lc.line, obj.lc.col
    if len(path) < 1:
        return None
    obj = path_to_obj(tree, list(path)[:-1])
    if isinstance(obj, ruamel.yaml.comments.CommentedBase):
        return obj.lc.key(path[-1])
    return None

def load_schema(schema, preserve_comments=True):
    data = pkgutil.get_data('dtschema', schema).decode('utf-8')
    if not preserve_comments:
        data = re.sub(r'^(\s|)*#.*\n', r'', data, flags=re.MULTILINE)
    return ruamel.yaml.load(data, Loader=ruamel.yaml.RoundTripLoader)

def _value_is_type(subschema, key, type):
    if not ( isinstance(subschema, dict) and key in subschema.keys() ):
        return False

    if isinstance(subschema[key], list):
        val = subschema[key][0]
    else:
        val = subschema[key]

    return isinstance(val, type)


def _fixup_string_to_array(subschema, match):
    if not _value_is_type(subschema, match, str):
        return

    subschema.insert(0, 'items', [CommentedMap([(match, subschema[match])]) ])
    subschema.pop(match, None)

def _fixup_scalar_to_array(subschema, match):
    if not _value_is_type(subschema, match, int):
        return

    subschema.insert(0, 'items',
        ([ CommentedMap([('items', [CommentedMap([(match, subschema[match])]) ]) ]) ]) )
    subschema.pop(match, None)

def _fixup_items_size(schema):
    # Make items list fixed size-spec
    if isinstance(schema, list):
        for l in schema:
            _fixup_items_size(l)
    elif isinstance(schema, dict):
        if 'items' in schema.keys() and isinstance(schema['items'], list):
            if not schema.keys() & {'minItems', 'maxItems', 'additionalItems'}:
                c = len(schema['items'])
                schema.insert(0, 'minItems', c)
                schema.insert(0, 'maxItems', c)
                schema.insert(0, 'additionalItems', False)

        for prop,val in schema.items():
            _fixup_items_size(val)


def fixup_schema(schema):
    if not isinstance(schema, dict):
        return
    if 'properties' in schema.keys():
        fixup_props(schema[ 'properties' ])
    if 'patternProperties' in schema.keys():
        fixup_props(schema[ 'patternProperties' ])

def fixup_props(props):
    # Convert a single value to a matrix
    for prop,val in props.items():
        _fixup_string_to_array(val, 'const')
        _fixup_string_to_array(val, 'enum')
        _fixup_scalar_to_array(val, 'const')
        _fixup_scalar_to_array(val, 'enum')

    # Make items list fixed size-spec
    _fixup_items_size(props)

    for prop in props.keys():
        fixup_schema(props[prop])

    #ruamel.yaml.dump(props, sys.stdout, Dumper=ruamel.yaml.RoundTripDumper)

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

def add_select_schema(schema):
    '''Get a schema to be used in select tests.

    If the provided schema has a 'select' property, then use that as the select schema.
    If it has a compatible property, then create a select schema from that.
    If it has neither, then return a match-nothing schema
    '''
    if "select" in schema.keys():
        return

    if not 'compatible' in schema['properties'].keys():
        schema['select'] = False
        return

    compatible_list = [ ]
    for l in item_generator(schema['properties']['compatible'], 'enum'):
        compatible_list.extend(l)

    for l in item_generator(schema['properties']['compatible'], 'const'):
        compatible_list.extend(l)

    compatible_list = list(set(compatible_list))

    if len(compatible_list) != 0:
        schema['select'] = {
            'required': ['compatible'],
            'properties': {'compatible': {'contains': {'enum': compatible_list}}}}

def process_schema(filename):
    try:
        schema = load_schema(filename, preserve_comments=False)
    except ruamel.yaml.error.YAMLError as exc:
        print(filename + ": ignoring, error parsing file")
        return

    # Check that the validation schema is valid
    try:
        DTValidator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        print(filename + ": ignoring, error in schema '%s'" % exc.path[-1])
        #print(exc.message)
        return

    # Remove parts not necessary for validation
    schema.pop('examples', None)
    schema.pop('maintainers', None)
    schema.pop('historical', None)
    schema.pop('description', None)

    if not 'properties' in schema.keys():
        return schema

    schema['properties'].insert(0, '$nodename', True )

    add_select_schema(schema)
    if not 'select' in schema.keys():
        return

    schema["$filename"] = filename
    return schema

def process_schemas(user_schema_path):
    schemas = []

    schema_path = os.path.dirname(os.path.realpath(__file__))
    for filename in glob.iglob(os.path.join(schema_path, "schemas/**/*.yaml"), recursive=True):
        sch = process_schema(os.path.relpath(filename, schema_path))
        if sch:
            schemas.append(sch)
    count = len(schemas)
    if count == 0:
        print("error: no core schema found in path: %s/schemas" % schema_path)
        return

    if os.path.isdir(user_schema_path):
        for filename in glob.iglob(os.path.join(os.path.abspath(user_schema_path), "**/*.yaml"), recursive=True):
            sch = process_schema(os.path.relpath(filename, schema_path))
            if sch:
                schemas.append(sch)

        if count == len(schemas):
            print("warning: no schema found in path: %s" % user_schema_path)

    return schemas

def load(stream):
    return ruamel.yaml.load(stream, Loader=ruamel.yaml.RoundTripLoader)

def http_handler(uri):
    '''Custom handler for http://devicetre.org YAML references'''
    if schema_base_url in uri:
        return load_schema(uri.replace(schema_base_url, ''))
    return ruamel.yaml.load(jsonschema.compat.urlopen(uri).read().decode('utf-8'),
                            Loader=ruamel.yaml.RoundTripLoader)

handlers = {"http": http_handler}

class DTValidator(jsonschema.Draft6Validator):
    '''Custom Validator for Devicetree Schemas

    Overrides the Draft6 metaschema with the devicetree metaschema. This
    validator is used in exactly the same way as the Draft6Validator. Schema
    files can be validated with the .check_schema() method, and .validate()
    will check the data in a devicetree file.
    '''
    META_SCHEMA = load_schema('meta-schemas/core.yaml')

    def __init__(self, schema, types=()):
        resolver = jsonschema.RefResolver.from_schema(schema, handlers=handlers)
        format_checker = jsonschema.FormatChecker()
        jsonschema.Draft6Validator.__init__(self, schema, types, resolver=resolver,
                                            format_checker=format_checker)

    @classmethod
    def iter_schema_errors(cls, schema):
        for error in cls(cls.META_SCHEMA).iter_errors(schema):
            error.linecol = get_line_col(schema, error.path)
            yield error

    def iter_errors(self, instance, _schema=None):
        for error in jsonschema.Draft6Validator.iter_errors(self, instance, _schema):
            error.linecol = get_line_col(instance, error.path)
            yield error

    @classmethod
    def check_schema(cls, schema):
        for error in cls(cls.META_SCHEMA).iter_errors(schema):
            raise jsonschema.SchemaError.create_from(error)
        fixup_schema(schema)


def format_error(filename, error, verbose=False):
    src = os.path.abspath(filename) + ':'
    if error.linecol:
        src = src + '%i:%i:'%(error.linecol[0]+1, error.linecol[1]+1)

    if error.path:
        src += " " + error.path[0] + ":"
        if len(error.path) > 1:
            src += str(error.path[1]) + ":"

    if verbose:
        msg = str(error)
    else:
        msg = error.message

    return src + ' ' + msg
