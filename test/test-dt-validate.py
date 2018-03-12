#!/usr/bin/env python3
#
# Testcases for the Devicetree schema files and validation library
#
# Copyright 2018 Arm Ltd.
#
# SPDX-License-Identifier: BSD-2-Clause
#
# Testcases are executed by running 'make test' from the top level directory of this repo.

import unittest
import os
import glob
import sys
basedir = os.path.dirname(__file__)
import yaml
sys.path.insert(0, os.path.join(basedir, "../jsonschema-draft6"))
import jsonschema
sys.path.insert(0, os.path.join(basedir, ".."))
import dtschema

#validator = dtschema.DTValidator()

class TestDTMetaSchema(unittest.TestCase):
    def setUp(self):
        self.schema = dtschema.load_schema('test/schemas/good-example.yaml')
        self.bad_schema = dtschema.load_schema('test/schemas/bad-example.yaml')
        self.validator = dtschema.DTMetaValidator()

    def test_required_properties(self):
        self.validator.validate(self.schema)

    def test_required_property_missing(self):
        for key in self.schema.keys():
            if key in ['$id', 'properties', 'required', 'examples']:
                continue
            with self.subTest(k=key):
                schema_tmp = self.schema.copy()
                del schema_tmp[key]
                self.assertRaises(jsonschema.ValidationError, self.validator.validate, schema_tmp)

    def test_bad_schema(self):
        '''bad-example.yaml is all bad. There is no condition where it should pass validation'''
        self.assertRaises(jsonschema.ValidationError, self.validator.validate, self.bad_schema)

    def test_bad_properties(self):
        for key in self.bad_schema.keys():
            if key == 'properties':
                continue

            with self.subTest(k=key):
                schema_tmp = self.schema.copy()
                schema_tmp[key] = self.bad_schema[key]
                self.assertRaises(jsonschema.ValidationError, self.validator.validate, schema_tmp)

        bad_props = self.bad_schema['properties']
        schema_tmp = self.schema.copy()
        for key in bad_props.keys():
            with self.subTest(k="properties/"+key):
                schema_tmp['properties'] = self.schema['properties'].copy()
                schema_tmp['properties'][key] = bad_props[key]
                self.assertRaises(jsonschema.ValidationError, self.validator.validate, schema_tmp)

class TestDTSchema(unittest.TestCase):
    def test_binding_schemas_valid(self):
        '''Test that all schema files under ./schemas/ validate against the DT metaschema'''
        validator = dtschema.DTMetaValidator()
        for filename in glob.iglob('schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                validator.validate(schema)

if __name__ == '__main__':
    unittest.main()
