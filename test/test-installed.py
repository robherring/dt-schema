# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2026 dt-schema contributors
"""Smoke-test an installed wheel from outside its source/build directory."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import dtschema


REPO = Path(__file__).resolve().parent.parent
NATIVE = os.environ.get('DTSCHEMA_TEST_BACKEND', 'rust') == 'rust'
MODULES = {
    'dt-validate': 'dtb_validate',
    'dt-doc-validate': 'doc_validate',
    'dt-mk-schema': 'mk_schema',
    'dt-check-compatible': 'check_compatible',
    'dt-extract-example': 'extract_example',
}


class TestInstalledWheel(unittest.TestCase):
    def test_installed_commands(self):
        package = Path(dtschema.__file__).resolve().parent
        self.assertNotEqual(package, REPO / 'dtschema', 'Run this test against an installed wheel')
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)

            def run(command, *args, python=False):
                env = os.environ.copy()
                env.pop('DTSCHEMA_DIR', None)
                if python:
                    code = f'from dtschema.{MODULES[command]} import main; import sys; sys.exit(main())'
                    argv = [sys.executable, '-c', code]
                else:
                    executable = shutil.which(command)
                    self.assertIsNotNone(executable, command)
                    argv = [executable]
                    if NATIVE:
                        # A Python launcher would fail with this environment.
                        env['PYTHONHOME'] = str(work / 'no-python')
                        env['PATH'] = str(work)
                result = subprocess.run([*argv, *map(str, args)], cwd=work, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result

            for command in MODULES:
                executable = shutil.which(command)
                self.assertIsNotNone(executable, command)
                with open(executable, 'rb') as script:
                    self.assertEqual(script.read(2) == b'#!', not NATIVE, command)
                run(command, '--help')

            for command in ('dt-validate', 'dt-doc-validate', 'dt-mk-schema'):
                self.assertEqual(run(command, '--version').stdout.strip(), dtschema.__version__)
            for command in ('dt-validate', 'dt-mk-schema'):
                version_args = work / 'version-args'
                version_args.write_text('--version\n')
                self.assertEqual(run(command, f'@{version_args}').stdout.strip(), dtschema.__version__)

            schema = work / 'processed.json'
            args = work / 'args'
            json_flag = '--legacy-json' if NATIVE else '-j'
            args.write_text(f'{json_flag}\n-o\n{schema}\n{REPO / "test/schemas"}\n')
            run('dt-mk-schema', f'@{args}')
            processed = json.loads(schema.read_text())
            self.assertEqual(processed['version'], dtschema.__version__)
            core = processed['http://devicetree.org/schemas/root-node.yaml']
            self.assertTrue(Path(core['$filename']).is_relative_to(package))
            # Python must be able to consume JSON produced by the native command.
            validator = dtschema.DTValidator([str(schema)])
            self.assertIn('vendor,soc1-ip', validator.compat_map)
            for python in (False, True):
                run('dt-validate', '-s', schema, python=python)
                self.assertEqual(run('dt-check-compatible', '-s', schema, 'vendor,soc1-ip',
                                     python=python).stdout, 'vendor,soc1-ip\n')
                run('dt-doc-validate', REPO / 'test/schemas/good-example.yaml', python=python)

            sources = [schema]
            if NATIVE:
                indexed = work / 'processed.indexed'
                run('dt-mk-schema', '-j', '-o', indexed, REPO / 'test/schemas')
                self.assertTrue(indexed.read_bytes().startswith(b'DTSIDX01'))
                run('dt-validate', '-s', indexed)
                self.assertEqual(run('dt-check-compatible', '-s', indexed, 'vendor,soc1-ip').stdout,
                                 'vendor,soc1-ip\n')
                sources.append(indexed)

            example = REPO / 'rust/cli/dt-extract-example/tests/fixtures/with_examples.yaml'
            self.assertEqual(run('dt-extract-example', example).stdout,
                             run('dt-extract-example', example, python=True).stdout)

            if shutil.which('dtc'):
                dtb = work / 'device.dtb'
                subprocess.run(['dtc', '-Odtb', '-o', str(dtb), str(REPO / 'test/device.dts')],
                               check=True, capture_output=True)
                for source in sources:
                    run('dt-validate', '-s', source, dtb)


if __name__ == '__main__':
    unittest.main()
