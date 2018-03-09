# Python library for Devicetree schema validation
import sys
import os
import yaml
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "jsonschema-draft6"))
import jsonschema

schema_base_url = "http://devicetree.org"

def http_handler(uri):
    '''Custom handler for http://devicetre.org YAML references'''
    if schema_base_url in uri:
        f = open(uri.replace(schema_base_url, os.getcwd()))
        yamlfile = f.read()
        f.close()
    else:
        yamlfile = jsonschema.compat.urlopen(uri).read().decode("utf-8")
    return yaml.load(yamlfile)

handlers = {"http": http_handler}

def DTValidator():
    f = open("schemas/dt-core.yaml")
    schema = yaml.load(f.read())
    f.close()

    resolver = jsonschema.RefResolver.from_schema(schema, handlers=handlers)
    return jsonschema.Draft6Validator(schema, resolver=resolver)

def DTMetaValidator():
    f = open("meta-schemas/core.yaml")
    schema = yaml.load(f.read())
    f.close()

    resolver = jsonschema.RefResolver.from_schema(schema, handlers=handlers)
    return jsonschema.Draft6Validator(schema, resolver=resolver)
