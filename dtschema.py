# Python library for Devicetree schema validation
import sys
import os
import ruamel.yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "jsonschema-draft6"))
import jsonschema
import pkgutil

schema_base_url = "http://devicetree.org/"

yaml = ruamel.yaml.YAML()

def load_schema(schema):
    return yaml.load(pkgutil.get_data('dtschema', schema).decode('utf-8'))

def http_handler(uri):
    '''Custom handler for http://devicetre.org YAML references'''
    if schema_base_url in uri:
        return load_schema(uri.replace(schema_base_url, ''))
    return yaml.load(jsonschema.compat.urlopen(uri).read().decode('utf-8'))

handlers = {"http": http_handler}

class DTValidator(jsonschema.Draft6Validator):
    '''Custom Validator for Devicetree Schemas

    Overrides the Draft6 metaschema with the devicetree metaschema. This
    validator is used in exactly the same way as the Draft6Validator. Schema
    files can be validated with the .check_schema() method, and .validate()
    will check the data in a devicetree file.
    '''
    META_SCHEMA = load_schema('meta-schemas/core.yaml')

    def __init__(self, schema, types=(), format_checker=None):
        resolver = jsonschema.RefResolver.from_schema(schema, handlers=handlers)
        jsonschema.Draft6Validator.__init__(self, schema, types, resolver=resolver,
                                            format_checker=format_checker)

    @classmethod
    def iter_schema_errors(cls, schema):
        return cls(cls.META_SCHEMA).iter_errors(schema)

