# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2018 Linaro Ltd.
# Copyright 2018-2023 Arm Ltd.

import os
import sys
import re
import copy
import glob
import json
import jsonschema
import ruamel.yaml

from jsonschema.exceptions import RefResolutionError

import dtschema
from dtschema.lib import _is_string_schema
from dtschema.lib import _get_array_range
from dtschema.schema import DTSchema

schema_basedir = os.path.dirname(os.path.abspath(__file__))


def _merge_dim(dim1, dim2):
    d = []
    for i in range(0, 2):
        if dim1[i] == (0, 0):
            d.insert(i, dim2[i])
        elif dim2[i] == (0, 0):
            d.insert(i, dim1[i])
        else:
            d.insert(i, (min(dim1[i] + dim2[i]), max(dim1[i] + dim2[i])))

    return tuple(d)


type_re = re.compile('(flag|u?int(8|16|32|64)(-(array|matrix))?|string(-array)?|phandle(-array)?)')


def _extract_prop_type(props, schema, propname, subschema, is_pattern):
    if not isinstance(subschema, dict):
        return

    if propname.startswith('$'):
        return

    # We only support local refs
    if '$ref' in subschema and subschema['$ref'].startswith('#/'):
        sch_path = subschema['$ref'].split('/')[1:]
        tmp_subschema = schema
        for p in sch_path:
            tmp_subschema = tmp_subschema[p]
        #print(propname, sch_path, tmp_subschema, file=sys.stderr)
        _extract_prop_type(props, schema, propname, tmp_subschema, is_pattern)

    for k in subschema.keys() & {'allOf', 'oneOf', 'anyOf'}:
        for v in subschema[k]:
            _extract_prop_type(props, schema, propname, v, is_pattern)

    props.setdefault(propname, [])

    new_prop = {}
    prop_type = None

    if ('type' in subschema and subschema['type'] == 'object') or \
       subschema.keys() & {'properties', 'patternProperties', 'additionalProperties'}:
        prop_type = 'node'
    else:
        try:
            prop_type = type_re.search(subschema['$ref']).group(0)
        except:
            if 'type' in subschema and subschema['type'] == 'boolean':
                prop_type = 'flag'
            elif 'items' in subschema:
                items = subschema['items']
                if (isinstance(items, list) and _is_string_schema(items[0])) or \
                   (isinstance(items, dict) and _is_string_schema(items)):
                    # implicit string type
                    prop_type = 'string-array'
                elif not (isinstance(items, list) and len(items) == 1 and
                          'items' in items and isinstance(items['items'], list) and
                          len(items['items']) == 1):
                    # Keep in sync with property-units.yaml
                    if re.search('-microvolt$', propname):
                        prop_type = 'int32-matrix'
                    elif re.search('(^(?!opp)).*-hz$', propname):
                        prop_type = 'uint32-matrix'
                    else:
                        prop_type = None
                else:
                    prop_type = None
            elif '$ref' in subschema and re.search(r'\.yaml#?$', subschema['$ref']):
                prop_type = 'node'
            else:
                prop_type = None

    new_prop['type'] = prop_type
    new_prop['$id'] = [schema['$id']]
    if is_pattern:
        new_prop['regex'] = re.compile(propname)

    if not prop_type:
        if len(props[propname]) == 0:
            props[propname] += [new_prop]
        return

    # handle matrix dimensions
    if prop_type == 'phandle-array' or prop_type.endswith('-matrix'):
        dim = (_get_array_range(subschema), _get_array_range(subschema.get('items', {})))
        new_prop['dim'] = dim
    else:
        dim = ((0, 0), (0, 0))

    dup_prop = None
    for p in props[propname]:
        if p['type'] is None:
            dup_prop = p
            break
        if dim != ((0, 0), (0, 0)) and \
           (p['type'] == 'phandle-array' or p['type'].endswith('-matrix')):
            if 'dim' not in p:
                p['dim'] = dim
            elif p['dim'] != dim:
                # Conflicting dimensions
                p['dim'] = _merge_dim(p['dim'], dim)
            return
        if p['type'].startswith(prop_type):
            # Already have the same or looser type, just record the $id
            new_prop = None
            if schema['$id'] not in p['$id']:
                p['$id'] += [schema['$id']]
            break
        elif p['type'] in prop_type:
            # Replace scalar type with array type
            new_prop['$id'] += p['$id']
            dup_prop = p
            break

    if dup_prop:
        props[propname].remove(dup_prop)

    if new_prop:
        props[propname] += [new_prop]

    if subschema.keys() & {'properties', 'patternProperties', 'additionalProperties'}:
        _extract_subschema_types(props, schema, subschema)


def _extract_subschema_types(props, schema, subschema):
    if not isinstance(subschema, dict):
        return

    if 'additionalProperties' in subschema:
        _extract_subschema_types(props, schema, subschema['additionalProperties'])

    for k in subschema.keys() & {'properties', 'patternProperties'}:
        if isinstance(subschema[k], dict):
            for p, v in subschema[k].items():
                _extract_prop_type(props, schema, p, v, k == 'patternProperties')


def extract_types(schemas):
    props = {}
    for sch in schemas.values():
        _extract_subschema_types(props, sch, sch)

    return props


def get_prop_types(schemas, want_missing_types=False, want_node_types=False):
    pat_props = {}

    props = extract_types(schemas)

    # hack to remove aliases and generic patterns
    del props['^[a-z][a-z0-9\-]*$']
    props.pop('^[a-zA-Z][a-zA-Z0-9\\-_]{0,63}$', None)
    props.pop('^.*$', None)
    props.pop('.*', None)

    # Remove node types
    if not want_node_types:
        for val in props.values():
            val[:] = [t for t in val if t['type'] != 'node']

    # Remove all properties without a type
    if not want_missing_types:
        for val in props.values():
            val[:] = [t for t in val if t['type'] is not None]

    # Delete any entries now empty due to above operations
    for key in [key for key in props if len(props[key]) == 0]:
        del props[key]

    # Split out pattern properties
    for key in [key for key in props if len(props[key]) and 'regex' in props[key][0]]:
        # Only want patternProperties with type and some amount of fixed string
        if re.search(r'[0-9a-zA-F-]{3}', key):
            #print(key, props[key], file=sys.stderr)
            pat_props[key] = props[key]
        del props[key]

    return [props, pat_props]


def make_compatible_schema(schemas):
    compat_sch = [{'enum': []}]
    compatible_list = set()
    for sch in schemas.values():
        compatible_list |= dtschema.extract_compatibles(sch)

    # Allow 'foo' values for examples
    compat_sch += [{'pattern': '^foo'}]

    prog = re.compile('.*[\^\[{\(\$].*')
    for c in compatible_list:
        if prog.match(c):
            # Exclude the generic pattern
            if c != '^[a-zA-Z0-9][a-zA-Z0-9,+\-._/]+$':
                compat_sch += [{'pattern': c}]
        else:
            compat_sch[0]['enum'].append(c)

    compat_sch[0]['enum'].sort()
    schemas['generated-compatibles'] = {
        '$id': 'http://devicetree.org/schemas/generated-compatibles',
        '$filename': 'Generated schema of documented compatible strings',
        'select': True,
        'properties': {
            'compatible': {
                'items': {
                    'anyOf': compat_sch
                }
            }
        }
    }


def process_schema(filename):
    try:
        dtsch = DTSchema(filename)
    except:
        print(f"{filename}: ignoring, error parsing file", file=sys.stderr)
        return

    # Check that the validation schema is valid
    try:
        dtsch.is_valid()
    except jsonschema.SchemaError as exc:
        print(f"{filename}: ignoring, error in schema: " + ': '.join(str(x) for x in exc.path),
              file=sys.stderr)
        #print(exc.message)
        return

    schema = dtsch.fixup()
    if 'select' not in schema:
        print(f"{filename}: warning: no 'select' found in schema found", file=sys.stderr)
        return

    schema["type"] = "object"
    schema["$filename"] = filename
    return schema


def process_schemas(schema_paths, core_schema=True):
    schemas = {}

    for filename in schema_paths:
        if not os.path.isfile(filename):
            continue
        sch = process_schema(os.path.abspath(filename))
        if not sch or '$id' not in sch:
            continue
        if sch['$id'] in schemas:
            print(f"{os.path.abspath(filename)}: duplicate '$id' value '{sch['$id']}'", file=sys.stderr)
        else:
            schemas[sch['$id']] = sch

    if core_schema:
        schema_paths.append(os.path.join(schema_basedir, 'schemas/'))

    for path in schema_paths:
        count = 0
        if not os.path.isdir(path):
            continue

        for filename in glob.iglob(os.path.join(os.path.abspath(path), "**/*.yaml"), recursive=True):
            sch = process_schema(os.path.abspath(filename))
            if sch:
                count += 1
                if sch['$id'] in schemas:
                    print(f"{os.path.abspath(filename)}: duplicate '$id' value '{sch['$id']}'", file=sys.stderr)
                else:
                    schemas[sch['$id']] = sch

        if count == 0:
            print(f"warning: no schema found in path: {path}", file=sys.stderr)

    return schemas


def typeSize(validator, typeSize, instance, schema):
    try:
        size = instance[0][0].size
    except:
        size = 32

    if typeSize != size:
        yield jsonschema.ValidationError("size is %r, expected %r" % (size, typeSize))


class DTValidator:
    '''Custom Validator for Devicetree Schemas

    Overrides the Draft7 metaschema with the devicetree metaschema. This
    validator is used in exactly the same way as the Draft7Validator. Schema
    files can be validated with the .check_schema() method, and .validate()
    will check the data in a devicetree file.
    '''
    DtValidator = jsonschema.validators.extend(jsonschema.Draft201909Validator, {'typeSize': typeSize})

    def __init__(self, schema_files, filter=None):
        self.schemas = {}
        self.resolver = jsonschema.RefResolver('', None, handlers={'http': self.http_handler})

        yaml = ruamel.yaml.YAML(typ='safe')

        if len(schema_files) == 1 and os.path.isfile(schema_files[0]):
            # a processed schema file
            with open(schema_files[0], 'r', encoding='utf-8') as f:
                if schema_files[0].endswith('.json'):
                    schema_cache = json.load(f)
                else:
                    schema_cache = yaml.load(f.read())

            # Convert old format to new
            if isinstance(schema_cache, list):
                d = {}
                for sch in schema_cache:
                    if not isinstance(sch, dict):
                        return None
                    d[sch['$id']] = sch
                schema_cache = d

            if 'generated-types' in schema_cache:
                self.props = schema_cache['generated-types']['properties']
            if 'generated-pattern-types' in schema_cache:
                self.pat_props = copy.deepcopy(schema_cache['generated-pattern-types']['properties'])
                for k in self.pat_props:
                    self.pat_props[k][0]['regex'] = re.compile(k)

            self.schemas = schema_cache
        else:
            self.schemas = process_schemas(schema_files)
            self.make_property_type_cache()
            make_compatible_schema(self.schemas)
            for k in self.pat_props:
                self.pat_props[k][0]['regex'] = re.compile(k)

    def http_handler(self, uri):
        '''Custom handler for http://devicetree.org references'''
        try:
            uri += '#'
            if uri in self.schemas:
                return self.schemas[uri]
            else:
                # If we have a schema_cache, then the schema should have been there unless the schema had errors
                if len(self.schemas):
                    return False
        except:
            raise RefResolutionError('Error in referenced schema matching $id: ' + uri)

    def annotate_error(self, id, error):
        error.schema_file = id
        error.linecol = -1, -1
        error.note = None

    def iter_errors(self, instance, filter=None):
        for id, schema in self.schemas.items():
            if 'select' not in schema:
                continue
            if filter and filter not in id:
                continue
            sch = {'if': schema['select'], 'then': schema}
            for error in self.DtValidator(sch,
                                          resolver=self.resolver,
                                          ).iter_errors(instance):
                self.annotate_error(id, error)
                yield error

    def validate(self, instance, filter=None):
        for error in self.iter_errors(instance, filter=filter):
            raise error

    def get_undocumented_compatibles(self, compatible_list):
        undoc_compats = []

        validator = self.DtValidator(self.schemas['generated-compatibles'])
        for compat in compatible_list:
            if not validator.is_valid({"compatible": [compat]}):
                undoc_compats += [compat]

        return undoc_compats

    def make_property_type_cache(self):
        self.props, self.pat_props = get_prop_types(self.schemas)

        for val in self.props.values():
            for t in val:
                del t['$id']

        self.schemas['generated-types'] = {
            '$id': 'generated-types',
            '$filename': 'Generated property types',
            'select': False,
            'properties': {k: self.props[k] for k in sorted(self.props)}
        }

        pat_props = copy.deepcopy(self.pat_props)
        for val in pat_props.values():
            for t in val:
                t.pop('regex', None)
                del t['$id']

        self.schemas['generated-pattern-types'] = {
            '$id': 'generated-pattern-types',
            '$filename': 'Generated pattern property types',
            'select': False,
            'properties': {k: pat_props[k] for k in sorted(pat_props)}
        }

    def property_get_all(self):
        all_props = copy.deepcopy({**self.props, **self.pat_props})
        for p, v in all_props.items():
            v[0].pop('regex', None)

        return all_props

    def property_get_type(self, propname):
        ptype = set()
        if propname in self.props:
            for v in self.props[propname]:
                if v['type']:
                    ptype.add(v['type'])
        if len(ptype) == 0:
            for v in self.pat_props.values():
                if v[0]['type'] and v[0]['type'] not in ptype and v[0]['regex'].search(propname):
                    ptype.add(v[0]['type'])

        # Don't return 'node' as a type if there's other types
        if len(ptype) > 1 and 'node' in ptype:
            ptype -= {'node'}
        return ptype

    def property_get_type_dim(self, propname):
        if propname in self.props:
            for v in self.props[propname]:
                if 'dim' in v:
                    return v['dim']

        for v in self.pat_props.values():
            if v[0]['type'] and 'dim' in v[0] and v[0]['regex'].search(propname):
                return v[0]['dim']

        return None

    def property_has_fixed_dimensions(self, propname):
        dim = self.property_get_type_dim(propname)
        if dim and dim[0][0] == dim[0][1] or dim[1][0] == dim[1][1]:
            return True

        return False

    def decode_dtb(self, dtb):
        return [dtschema.dtb.fdt_unflatten(self, dtb)]
