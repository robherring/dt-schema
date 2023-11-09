#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2023 Arm Ltd.

import sys
import argparse
import urllib

import dtschema


def path_list_to_str(path):
    return '/' + '/'.join(path)


def prop_generator(schema, path=[]):
    if not isinstance(schema, dict):
        return
    for prop_key in ['properties', 'patternProperties']:
        if prop_key in schema:
            for p, sch in schema[prop_key].items():
                yield path + [prop_key, p], sch
                yield from prop_generator(sch, path=path + [prop_key, p])


def _ref_to_id(id, ref):
    ref = urllib.parse.urljoin(id, ref)
    if '#/' not in ref:
        ref += '#'
    return ref


def _prop_in_schema(prop, schema, schemas):
    for p, sch in prop_generator(schema):
        if p[1] == prop:
            return True

    if 'allOf' in schema:
        for e in schema['allOf']:
            if '$ref' in e:
                ref_id = _ref_to_id(schema['$id'], e['$ref'])
                if ref_id in schemas:
                    if _prop_in_schema(prop, schemas[ref_id], schemas):
                        return True

    if '$ref' in schema:
        ref_id = _ref_to_id(schema['$id'], schema['$ref'])
        if ref_id in schemas and _prop_in_schema(prop, schemas[ref_id], schemas):
            return True

    return False


def check_removed_property(id, base, schemas):
    for p, sch in prop_generator(base):
        if not _prop_in_schema(p[1], schemas[id], schemas):
            print(f'{id}{path_list_to_str(p)}: existing property removed\n', file=sys.stderr)


def schema_get_from_path(sch, path):
    for p in path:
        try:
            sch = sch[p]
        except:
            return None
    return sch


def check_new_items(id, base, new, path=[]):
    for p, sch in prop_generator(new):
        if not isinstance(sch, dict) or 'minItems' not in sch:
            continue

        min = sch['minItems']
        base_min = schema_get_from_path(base, p + ['minItems'])

        if base_min and min > base_min:
            print(f'{id}{path_list_to_str(p)}: new required entry added\n', file=sys.stderr)

def _get_required(schema):
    required = []
    for k in {'allOf', 'oneOf', 'anyOf'} & schema.keys():
        for sch in schema[k]:
            if 'required' not in sch:
                continue
            required += sch['required']

    if 'required' in schema:
        required += schema['required']

    return set(required)


def _check_required(id, base, new, path=[]):
    if not isinstance(base, dict) or not isinstance(new, dict):
        return

    base_req = _get_required(base)
    new_req = _get_required(new)

    if not new_req:
        return

    diff = new_req - base_req
    if diff:
        print(f'{id}{path_list_to_str(path)}: new required properties added: {", ".join(diff)}\n', file=sys.stderr)
        return


def check_required(id, base, new):
    _check_required(id, base, new)

    for p, sch in prop_generator(new):
        _check_required(id, schema_get_from_path(base, p), sch, path=p)


def main():
    ap = argparse.ArgumentParser(description="Compare 2 sets of schemas for possible ABI differences")
    ap.add_argument("baseline", type=str,
                    help="Baseline schema directory or preprocessed schema file")
    ap.add_argument("new", type=str,
                    help="New schema directory or preprocessed schema file")
    ap.add_argument('-V', '--version', help="Print version number",
                    action="version", version=dtschema.__version__)
    args = ap.parse_args()

    base_schemas = dtschema.DTValidator([args.baseline]).schemas
    schemas = dtschema.DTValidator([args.new]).schemas

    if not schemas or not base_schemas:
        return -1

    for id, sch in schemas.items():
        if id not in base_schemas or 'generated' in id:
            continue

        check_required(id, base_schemas[id], sch)
        check_removed_property(id, base_schemas[id], schemas)
        check_new_items(id, base_schemas[id], sch)
