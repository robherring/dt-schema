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
        self.schema = dtschema.load(os.path.join(basedir, 'schemas/good-example.yaml'),
            duplicate_keys=False)
        self.bad_schema = dtschema.load(os.path.join(basedir, 'schemas/bad-example.yaml'),
            duplicate_keys=False)

    def test_metaschema_valid(self):
        '''The DTValidator metaschema must be a valid Draft7 schema'''
        jsonschema.Draft7Validator.check_schema(dtschema.DTValidator.META_SCHEMA)

    def test_all_metaschema_valid(self):
        '''The metaschema must all be a valid Draft7 schema'''
        for filename in glob.iglob('meta-schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                jsonschema.Draft7Validator.check_schema(schema)

    def test_required_properties(self):
        dtschema.DTValidator.check_schema(self.schema)

    def test_required_property_missing(self):
        for key in self.schema.keys():
            if key in ['$schema', 'properties', 'required', 'description', 'examples', 'additionalProperties']:
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
            if key in ['$schema', 'properties']:
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
        for filename in glob.iglob('schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                dtschema.DTValidator.check_schema(schema)

    def test_binding_schemas_id_is_unique(self):
        '''Test that all schema files under ./schemas/ validate against the DT metaschema'''
        ids = []
        for filename in glob.iglob('schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                self.assertEqual(ids.count(schema['$id']), 0)
                ids.append(schema['$id'])

    def test_binding_schemas_valid_draft7(self):
        '''Test that all schema files under ./schemas/ validate against the Draft7 metaschema
        The DT Metaschema is supposed to force all schemas to be valid against
        Draft7. This test makes absolutely sure that they are.
        '''
        for filename in glob.iglob('schemas/**/*.yaml', recursive=True):
            with self.subTest(schema=filename):
                schema = dtschema.load_schema(filename)
                jsonschema.Draft7Validator.check_schema(schema)


class TestDTValidate(unittest.TestCase):
    def setUp(self):
        self.schemas = list()

        self.schemas = dtschema.process_schemas([ os.path.join(os.path.abspath(basedir), "schemas/")])

        for schema in self.schemas:
            schema["$select_validator"] = jsonschema.Draft7Validator(schema['select'])

    def check_node(self, nodename, node, fail):
        if nodename == "/":
            return

        node['$nodename'] = [ nodename ]
        node_matched = True
        if fail:
            node_matched = False
            with self.assertRaises(jsonschema.ValidationError, msg=nodename):
                for schema in self.schemas:
                    if schema['$select_validator'].is_valid(node):
                        node_matched = True
                        dtschema.DTValidator(schema).validate(node)
        else:
            node_matched = False
            for schema in self.schemas:
                if schema['$select_validator'].is_valid(node):
                    node_matched = True
                    self.assertIsNone(dtschema.DTValidator(schema).validate(node))

        self.assertTrue(node_matched, msg=nodename)

    def check_subtree(self, nodename, subtree, fail):
        self.check_node(nodename, subtree, fail)
        for name,value in subtree.items():
            if isinstance(value, dict):
                self.check_subtree(name, value, fail)


    def test_dt_validation(self):
        '''Test that all DT YAML files under ./test/ validate against the DT schema'''
        for filename in glob.iglob('test/*.yaml'):
            with self.subTest(schema=filename):
                expect_fail = "-fail" in filename
                testtree = dtschema.load(filename)[0]
                for name,value in testtree.items():
                    if isinstance(value, dict):
                        self.check_node(name, value, expect_fail)


if __name__ == '__main__':
    unittest.main()
