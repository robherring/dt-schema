# Python library for Devicetree schema validation
import sys
import os
import yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "jsonschema-draft6"))
import jsonschema
import pkgutil

schema_base_url = "http://devicetree.org/"

def http_handler(uri):
    '''Custom handler for http://devicetre.org YAML references'''
    if schema_base_url in uri:
        yamlfile = pkgutil.get_data("dtschema", uri.replace(schema_base_url, ""))
    else:
        yamlfile = jsonschema.compat.urlopen(uri).read()
    return yaml.load(yamlfile.decode("utf-8"))

handlers = {"http": http_handler}

def DTValidator(schema):
    resolver = jsonschema.RefResolver.from_schema(schema, handlers=handlers)
    return jsonschema.Draft6Validator(schema, resolver=resolver)

def DTMetaValidator():
    schema = yaml.load(pkgutil.get_data("dtschema", "meta-schemas/core.yaml").decode("utf-8"))

    resolver = jsonschema.RefResolver.from_schema(schema, handlers=handlers)
    return jsonschema.Draft6Validator(schema, resolver=resolver)
