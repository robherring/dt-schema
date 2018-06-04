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
import jsonschema
import dtschema

class TestDTMetaSchema(unittest.TestCase):
    def setUp(self):
        self.schema = dtschema.load(open(os.path.join(basedir, 'schemas/good-example.yaml'), encoding='utf-8').read())
        self.bad_schema = dtschema.load(open(os.path.join(basedir, 'schemas/bad-example.yaml'), encoding='utf-8').read())

    def test_metaschema_valid(self):
        '''The DTValidator metaschema must be a valid Draft6 schema'''
        jsonschema.Draft6Validator.check_schema(dtschema.DTValidator.META_SCHEMA)

    def test_all_metaschema_valid(self):
        '''The metaschema must all be a valid Draft6 schema'''
        for filename in glob.iglob('meta-schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                jsonschema.Draft6Validator.check_schema(schema)

    def test_required_properties(self):
        dtschema.DTValidator.check_schema(self.schema)

    def test_required_property_missing(self):
        for key in self.schema.keys():
            if key in ['properties', 'required', 'description', 'examples']:
                continue
            with self.subTest(k=key):
                schema_tmp = self.schema.copy()
                del schema_tmp[key]
                self.assertRaises(jsonschema.SchemaError, dtschema.DTValidator.check_schema, schema_tmp)

    def test_bad_schema(self):
        '''bad-example.yaml is all bad. There is no condition where it should pass validation'''
        self.assertRaises(jsonschema.SchemaError, dtschema.DTValidator.check_schema, self.bad_schema)

    def test_bad_properties(self):
        for key in self.bad_schema.keys():
            if key == 'properties':
                continue

            with self.subTest(k=key):
                schema_tmp = self.schema.copy()
                schema_tmp[key] = self.bad_schema[key]
                self.assertRaises(jsonschema.SchemaError, dtschema.DTValidator.check_schema, schema_tmp)

        bad_props = self.bad_schema['properties']
        schema_tmp = self.schema.copy()
        for key in bad_props.keys():
            with self.subTest(k="properties/"+key):
                schema_tmp['properties'] = self.schema['properties'].copy()
                schema_tmp['properties'][key] = bad_props[key]
                self.assertRaises(jsonschema.SchemaError, dtschema.DTValidator.check_schema, schema_tmp)

class TestDTSchema(unittest.TestCase):
    def test_binding_schemas_valid(self):
        '''Test that all schema files under ./schemas/ validate against the DT metaschema'''
        for filename in glob.iglob('../schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                dtschema.DTValidator.check_schema(schema)

    def test_binding_schemas_valid_draft6(self):
        '''Test that all schema files under ./schemas/ validate against the Draft6 metaschema
        The DT Metaschema is supposed to force all schemas to be valid against
        Draft6. This test makes absolutely sure that they are.
        '''
        for filename in glob.iglob('../schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                jsonschema.Draft6Validator.check_schema(schema)

if __name__ == '__main__':
    unittest.main()
