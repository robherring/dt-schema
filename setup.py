# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2026 dt-schema contributors

from distutils.command.build_scripts import build_scripts
from pathlib import Path
import sysconfig

from setuptools import setup
from setuptools.command.build import build
from setuptools_rust.build import build_rust


class Build(build):
    # Stage Python fallbacks first; successful RustBin builds replace them.
    sub_commands = [('build_scripts', build.has_scripts)] + [
        command for command in build.sub_commands if command[0] != 'build_scripts'
    ]


class BuildScripts(build_scripts):
    def run(self):
        # A previous native build may have left newer executable files behind.
        # Restore Python fallbacks even when this build has no Rust compiler.
        self.force = True
        super().run()


class BuildRust(build_rust):
    def run(self):
        super().run()
        scripts = self.get_finalized_command('build_scripts')
        suffix = sysconfig.get_config_var('EXE') or ''
        binaries = [Path(scripts.build_dir) / (Path(script).name + suffix)
                    for script in scripts.scripts]
        for binary in binaries:
            if binary.is_file():
                with binary.open('rb') as executable:
                    if executable.read(2) != b'#!':
                        continue
            # Keep the whole toolset on one implementation if any build fails.
            # In particular, Python cannot read Rust's indexed schema format.
            if suffix:
                for native in binaries:
                    native.unlink(missing_ok=True)
            scripts.run()
            break


setup(cmdclass={'build': Build, 'build_scripts': BuildScripts, 'build_rust': BuildRust})
