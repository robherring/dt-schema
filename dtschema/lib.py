# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2018 Linaro Ltd.
# Copyright 2018 Arm Ltd.
# Python library for Devicetree schema validation
import sys
import os
import glob
import ruamel.yaml
import re
import pprint
import json

import jsonschema

from jsonschema.exceptions import RefResolutionError

import dtschema.dtb

schema_base_url = "http://devicetree.org/"
schema_basedir = os.path.dirname(os.path.abspath(__file__))

# We use a lot of regex's in schema and exceeding the cache size has noticeable
# peformance impact.
re._MAXCACHE = 2048


class sized_int(int):
    def __new__(cls, value, *args, **kwargs):
        return int.__new__(cls, value)

    def __init__(self, value, size=32):
        self.size = size


rtyaml = ruamel.yaml.YAML(typ='rt')
rtyaml.allow_duplicate_keys = False
rtyaml.preserve_quotes = True

yaml = ruamel.yaml.YAML(typ='safe')
yaml.allow_duplicate_keys = False


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
        return -1, -1
    obj = path_to_obj(tree, list(path)[:-1])
    if isinstance(obj, ruamel.yaml.comments.CommentedBase):
        if path[-1] == '$nodename':
            return -1, -1
        return obj.lc.key(path[-1])
    return -1, -1


schema_user_paths = []


def add_schema_path(path):
    if os.path.isdir(path):
        schema_user_paths.append(os.path.abspath(path))


def check_id_path(filename, id):
    id = id.replace('http://devicetree.org/schemas/', '')
    id = id.replace('#', '')

    base = os.path.abspath(filename)

    for p in schema_user_paths:
        base = base.replace(p + '/', '')

    base = base.replace(os.path.join(schema_basedir, 'schemas/'), '')
    base = base.replace(os.path.abspath('schemas/') + '/', '')

    if not id == base:
        print(filename +
              ": $id: relative path/filename doesn't match actual path or filename\n\texpected: http://devicetree.org/schemas/" +
              base + '#',
              file=sys.stderr)


def do_load(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        if filename.endswith('.json'):
            return json.load(f)

        return yaml.load(f.read())


def load_schema(schema):
    for path in schema_user_paths:
        if schema.startswith('schemas/'):
            schema_file = schema.partition('/')[2]
        else:
            schema_file = schema
        schema_file = os.path.join(path, schema_file)
        if not os.path.isfile(schema_file):
            continue

        return do_load(schema_file)

    return do_load(os.path.join(schema_basedir, schema))


def _value_is_type(subschema, key, type):
    if key not in subschema:
        return False

    if isinstance(subschema[key], list):
        val = subschema[key][0]
    else:
        val = subschema[key]

    return isinstance(val, type)


def _is_int_schema(subschema):
    for match in ['const', 'enum', 'minimum', 'maximum']:
        if _value_is_type(subschema, match, int):
            return True

    return False


def _is_string_schema(subschema):
    for match in ['const', 'enum', 'pattern']:
        if _value_is_type(subschema, match, str):
            return True

    return False


def extract_node_compatibles(schema):
    if not isinstance(schema, dict):
        return set()

    compatible_list = set()

    for l in item_generator(schema, 'enum'):
        if isinstance(l[0], str):
            compatible_list.update(l)

    for l in item_generator(schema, 'const'):
        compatible_list.update([str(l)])

    for l in item_generator(schema, 'pattern'):
        compatible_list.update([l])

    return compatible_list


def extract_compatibles(schema):
    if not isinstance(schema, dict):
        return set()

    compatible_list = set()
    for sch in item_generator(schema, 'compatible'):
        compatible_list.update(extract_node_compatibles(sch))

    return compatible_list


def item_generator(json_input, lookup_key):
    if isinstance(json_input, dict):
        for k, v in json_input.items():
            if k == lookup_key:
                yield v
            else:
                for child_val in item_generator(v, lookup_key):
                    yield child_val
    elif isinstance(json_input, list):
        for item in json_input:
            for item_val in item_generator(item, lookup_key):
                yield item_val


def make_compatible_schema(schemas):
    compat_sch = [{'enum': []}]
    compatible_list = set()
    for sch in schemas.values():
        compatible_list |= extract_compatibles(sch)

    # Allow 'foo' values for examples
    compat_sch += [{'pattern': '^foo'}]

    prog = re.compile('.*[\^\[{\(\$].*')
    for c in compatible_list:
        if prog.match(c):
            # Exclude the generic pattern
            if c != '^[a-zA-Z0-9][a-zA-Z0-9,+\-._]+$':
                compat_sch += [{'pattern': c}]
        else:
            compat_sch[0]['enum'].append(c)

    compat_sch[0]['enum'].sort()
    schemas['generated-compatibles'] = {
        '$id': 'generated-compatibles',
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


def get_undocumented_compatibles(compatible_list):
    global schema_cache
    undoc_compats = []

    validator = dtschema.DTValidator(schema_cache['generated-compatibles'])
    for compat in compatible_list:
        if not validator.is_valid({"compatible": [ compat ]}):
            undoc_compats += [ compat ]

    return undoc_compats


def process_schema(filename):
    try:
        schema = load_schema(filename)
    except ruamel.yaml.YAMLError:
        print(filename + ": ignoring, error parsing file", file=sys.stderr)
        return

    # Check that the validation schema is valid
    try:
        DTValidator.check_schema(schema, strict=False)
    except jsonschema.SchemaError as exc:
        print(filename + ": ignoring, error in schema: " + ': '.join(str(x) for x in exc.path),
              file=sys.stderr)
        #print(exc.message)
        return

    if 'select' not in schema:
        print(filename + ": warning: no 'select' found in schema found", file=sys.stderr)
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
            print(os.path.abspath(filename) + ": duplicate '$id' value '" + sch['$id'] + "'", file=sys.stderr)
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
                    print(os.path.abspath(filename) + ": duplicate '$id' value '" + sch['$id'] + "'", file=sys.stderr)
                else:
                    schemas[sch['$id']] = sch

        if count == 0:
            print("warning: no schema found in path: %s" % path, file=sys.stderr)

    make_compatible_schema(schemas)

    return schemas


def _get_array_range(subschema):
    if isinstance(subschema, list):
        if len(subschema) != 1:
            return (0, 0)
        subschema = subschema[0]
    if 'items' in subschema and isinstance(subschema['items'], list):
        max = len(subschema['items'])
        min = subschema.get('minItems', max)
    else:
        min = subschema.get('minItems', 1)
        max = subschema.get('maxItems', subschema.get('minItems', 0))

    return (min, max)


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
                elif not (isinstance(items, list) and len(items) == 1 and \
                     'items' in items and isinstance(items['items'], list) and len(items['items']) == 1):
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
        if dim != ((0, 0), (0, 0)) and (p['type'] == 'phandle-array' or p['type'].endswith('-matrix')):
            if not 'dim' in p:
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
            for p,v in subschema[k].items():
                _extract_prop_type(props, schema, p, v, k == 'patternProperties')


def extract_types():
    global schema_cache

    props = {}
    for sch in schema_cache.values():
        _extract_subschema_types(props, sch, sch)

    return props


def get_prop_types(want_missing_types=False, want_node_types=False):
    pat_props = {}

    props = dtschema.extract_types()

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
    for key in [key for key in props if len(props[key]) == 0]: del props[key]

    # Split out pattern properties
    for key in [key for key in props if len(props[key]) and 'regex' in props[key][0] ]:
        # Only want patternProperties with type and some amount of fixed string
        if re.search(r'[0-9a-zA-F-]{3}', key):
            #print(key, props[key], file=sys.stderr)
            pat_props[key] = props[key]
        del props[key]

    return [ props, pat_props ]


props = None
pat_props = None


def property_get_type(propname):
    global props
    global pat_props

    if not props:
        props, pat_props = get_prop_types()

    type = set()
    if propname in props:
        for v in props[propname]:
            if v['type']:
                type.add(v['type'])
    if len(type) == 0:
        for v in pat_props.values():
            if v[0]['type'] and v[0]['type'] not in type and v[0]['regex'].search(propname):
                type.add(v[0]['type'])

    # Don't return 'node' as a type if there's other types
    if len(type) > 1 and 'node' in type:
        type -= {'node'}
    return type


def property_get_type_dim(propname):
    global props
    global pat_props

    if not props:
        props, pat_props = get_prop_types()

    if propname in props:
        for v in props[propname]:
            if 'dim' in v:
                return v['dim']

    for v in pat_props.values():
        if v[0]['type'] and 'dim' in v[0] and v[0]['regex'].search(propname):
            return v[0]['dim']

    return None


def property_has_fixed_dimensions(propname):
    dim = property_get_type_dim(propname)
    if dim and dim[0][0] == dim[0][1] or dim[1][0] == dim[1][1]:
        return True

    return False


def load(filename, line_number=False):
    try:
        if not filename.endswith('.yaml'):
            with open(filename, 'rb') as f:
                return [ dtschema.dtb.fdt_unflatten(f.read()) ]
    except:
        if filename.endswith('.dtb'):
            raise

    with open(filename, 'r', encoding='utf-8') as f:
        if line_number:
            return rtyaml.load(f.read())
        else:
            return yaml.load(f.read())


def make_property_type_cache():
    global schema_cache

    props, pat_props = get_prop_types()

    for val in props.values():
        val[:] = [t for t in val if 'regex' not in t]
        for t in val: del t['$id']

    schema_cache['generated-types'] = {
        '$id': 'generated-types',
        '$filename': 'Generated property types',
        'select': False,
        'properties': {k: props[k] for k in sorted(props)}
    }

    for val in pat_props.values():
        for t in val:
            t.pop('regex', None)
            del t['$id']

    schema_cache['generated-pattern-types'] = {
        '$id': 'generated-pattern-types',
        '$filename': 'Generated property types',
        'select': False,
        'properties': {k: pat_props[k] for k in sorted(pat_props)}
    }


schema_cache = {}

def set_schemas(schema_files, core_schema=True):
    global schema_cache, pat_props, props

    if len(schema_files) == 1 and os.path.isfile(schema_files[0]):
        # a processed schema file
        schema_cache = dtschema.load_schema(os.path.abspath(schema_files[0]))
        # Convert old format to new
        if isinstance(schema_cache, list):
            d = {}
            for sch in schema_cache:
                if not isinstance(sch, dict):
                    return None
                d[sch['$id']] = sch
            schema_cache = d

        if 'generated-types' in schema_cache:
            props = schema_cache['generated-types']['properties']
        if 'generated-pattern-types' in schema_cache:
            pat_props = schema_cache['generated-pattern-types']['properties']
            for k in pat_props:
                pat_props[k][0]['regex'] = re.compile(k)
    else:
        schema_cache = process_schemas(schema_files, core_schema)
        make_property_type_cache()

    return schema_cache

def http_handler(uri):
    global schema_cache
    '''Custom handler for http://devicetre.org YAML references'''
    try:
        if schema_base_url in uri:
            my_uri = uri + '#'
            if my_uri in schema_cache:
                return schema_cache[my_uri]
            # If we have a schema_cache, then the schema should have been there unless the schema had errors
            if len(schema_cache):
                return False
            if 'meta-schemas' in uri:
                return load_schema(uri.replace(schema_base_url, ''))

            try:
                schema = load_schema(uri.replace(schema_base_url, ''))
            except Exception as exc:
                raise RefResolutionError('Unable to find schema file matching $id: ' + uri)

            try:
                DTValidator.check_schema(schema, strict=False)
            except Exception as exc:
                raise RefResolutionError('Error in referenced schema matching $id: ' + uri)

            return schema

        from urllib.request import urlopen

        return yaml.load(urlopen(uri).read().decode('utf-8'))
    except FileNotFoundError as e:
        print('Unknown file referenced:', e, file=sys.stderr)
        exit(-1)


handlers = {"http": http_handler}


def typeSize(validator, typeSize, instance, schema):
    try:
        size = instance[0][0].size
    except:
        size = 32

    if typeSize != size:
        yield jsonschema.ValidationError("size is %r, expected %r" % (size, typeSize))


class DTValidator():
    '''Custom Validator for Devicetree Schemas

    Overrides the Draft7 metaschema with the devicetree metaschema. This
    validator is used in exactly the same way as the Draft7Validator. Schema
    files can be validated with the .check_schema() method, and .validate()
    will check the data in a devicetree file.
    '''
    resolver = jsonschema.RefResolver('', None, handlers=handlers)
    format_checker = jsonschema.FormatChecker()
    DTVal = jsonschema.validators.extend(jsonschema.Draft201909Validator, {'typeSize': typeSize}, version='DT')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('resolver', self.resolver)
        kwargs.setdefault('format_checker', self.format_checker)
        self.validator = self.DTVal(*args, **kwargs)

    @classmethod
    def annotate_error(self, error, schema, path):
        error.note = None
        error.schema_file = None

        for e in error.context:
            self.annotate_error(e, schema, path + e.schema_path)

        scope = schema['$id']
        self.resolver.push_scope(scope)
        ref_depth = 1

        lastp = ''
        for p in path:
            # json-schema 3.2.0 includes 'if' in schema path
            if lastp != 'properties' and p == 'if':
                continue
            lastp = p

            while '$ref' in schema and isinstance(schema['$ref'], str):
                ref = self.resolver.resolve(schema['$ref'])
                schema = ref[1]
                self.resolver.push_scope(ref[0])
                ref_depth += 1

            if '$id' in schema and isinstance(schema['$id'], str):
                error.schema_file = schema['$id']

            schema = schema[p]

            if isinstance(schema, dict):
                if 'description' in schema and isinstance(schema['description'], str):
                    error.note = schema['description']

        while ref_depth > 0:
            self.resolver.pop_scope()
            ref_depth -= 1

        if isinstance(error.schema, dict) and 'description' in error.schema:
            error.note = error.schema['description']

    @classmethod
    def iter_schema_errors(cls, schema):
        try:
            meta_schema = cls.resolver.resolve_from_url(schema['$schema'])
        except (KeyError, TypeError, jsonschema.RefResolutionError, jsonschema.SchemaError):
            error = jsonschema.SchemaError("Missing or invalid $schema keyword")
            error.linecol = (-1,-1)
            yield error
            return
        val = cls.DTVal(meta_schema, resolver=cls.resolver)
        for error in val.iter_errors(schema):
            cls.annotate_error(error, meta_schema, error.schema_path)
            error.linecol = get_line_col(schema, error.path)
            yield error

    def iter_errors(self, instance, _schema=None):
        for error in self.validator.iter_errors(instance, _schema):
            yield error

    def validate(self, *args, **kwargs):
        for error in self.iter_errors(*args, **kwargs):
            raise error

    def is_valid(self, instance):
        error = next(self.iter_errors(instance), None)
        return error is None

    @classmethod
    def check_schema(cls, schema, strict=True):
        """
        Test if schema is valid and apply fixups
        'strict' determines whether the full DT meta-schema is used or just the draft7 meta-schema
        """
        if strict:
            meta_schema = cls.resolver.resolve_from_url(schema['$schema'])
        else:
            # Using the draft7 metaschema because 2019-09 with $recursiveRef seems broken
            meta_schema = jsonschema.Draft7Validator.META_SCHEMA
        val = cls.DTVal(meta_schema, resolver=cls.resolver)
        for error in val.iter_errors(schema):
            raise jsonschema.SchemaError.create_from(error)
        dtschema.fixup_schema(schema)

    @classmethod
    def _check_schema_refs(self, schema):
        if isinstance(schema, dict) and '$ref' in schema:
            self.resolver.resolve(schema['$ref'])
        elif isinstance(schema, dict):
            for k, v in schema.items():
                self._check_schema_refs(v)
        elif isinstance(schema, (list, tuple)):
            for i in range(len(schema)):
                self._check_schema_refs(schema[i])

    @classmethod
    def check_schema_refs(self, filename, schema):
        if '$id' not in schema:
            return
        scope = schema['$id']
        if scope:
            self.resolver.push_scope(scope)

        try:
            self._check_schema_refs(schema)
        except jsonschema.RefResolutionError as exc:
            print(filename + ':', exc, file=sys.stderr)

        check_id_path(filename, schema['$id'])


def format_error(filename, error, prefix="", nodename=None, verbose=False):
    src = prefix + os.path.abspath(filename) + ':'

    if hasattr(error, 'linecol') and error.linecol[0] >= 0:
        src = src + '%i:%i: ' % (error.linecol[0]+1, error.linecol[1]+1)
    else:
        src += ' '

    if nodename is not None:
        src += nodename + ': '

    if error.absolute_path:
        for path in error.absolute_path:
            src += str(path) + ":"
        src += ' '

    #print(error.__dict__)
    if verbose:
        msg = str(error)
    elif not error.schema_path:
        msg = error.message
    elif error.context:
        # An error on a conditional will have context with sub-errors
        msg = "'" + error.schema_path[-1] + "' conditional failed, one must be fixed:"

        for suberror in sorted(error.context, key=lambda e: e.path):
            if suberror.context:
                msg += '\n' + format_error(filename, suberror, prefix=prefix+"\t", nodename=nodename, verbose=verbose)
            elif suberror.message not in msg:
                msg += '\n' + prefix + '\t' + suberror.message
                if hasattr(suberror, 'note') and suberror.note and suberror.note != error.note:
                    msg += '\n\t\t' + prefix + 'hint: ' + suberror.note

    elif error.schema_path[-1] == 'oneOf':
        msg = 'More than one condition true in oneOf schema:\n\t' + \
            '\t'.join(pprint.pformat(error.schema, width=72).splitlines(True))

    else:
        msg = error.message

    if hasattr(error, 'note') and error.note:
        msg += '\n\t' + prefix + 'hint: ' + error.note

    if hasattr(error, 'schema_file') and error.schema_file:
        msg += '\n\t' + prefix + 'from schema $id: ' + error.schema_file

    return src + msg
