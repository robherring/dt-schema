# Python library for Devicetree schema validation
import sys
import os
import ruamel.yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "jsonschema-draft6"))
import jsonschema
import pkgutil
import rfc3987  # Not used by this module, but include here to enforce dependency

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

def load_schema(schema):
    return ruamel.yaml.load(pkgutil.get_data('dtschema', schema).decode('utf-8'),
                            Loader=ruamel.yaml.RoundTripLoader)

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

def format_error(filename, error, verbose=False):
    src = filename + ':'
    if error.linecol:
        src = src + '%i:%i:'%(error.linecol[0]+1, error.linecol[1]+1)

    if verbose:
        msg = str(error)
    else:
        msg = error.message

    return src + ' ' + msg
