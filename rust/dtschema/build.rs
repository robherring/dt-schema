// SPDX-License-Identifier: BSD-2-Clause
// Copyright 2026 dt-schema contributors

use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=PYTHON_SYS_EXECUTABLE");
    let Some(python) = std::env::var_os("PYTHON_SYS_EXECUTABLE") else {
        return;
    };
    // Record relative install paths at build time. Native commands must not
    // start Python to locate their schema data at runtime.
    let output = Command::new(python)
        .args([
            "-c",
            r#"
import os
import sysconfig

paths = []
user_scheme = 'nt_user' if os.name == 'nt' else 'posix_user'
for scheme in (None, user_scheme):
    config = sysconfig.get_paths(scheme=scheme) if scheme else sysconfig.get_paths()
    relative = os.path.relpath(os.path.join(config['platlib'], 'dtschema'), config['scripts'])
    paths.append(relative)
    if os.name != 'nt':
        for lib in ('lib', 'lib64'):
            for packages in ('site-packages', 'dist-packages'):
                parts = relative.split(os.sep)
                parts = [lib if p in ('lib', 'lib64') else packages if p == 'site-packages' else p
                         for p in parts]
                paths.append(os.sep.join(parts))
        paths.append('../lib/python3/dist-packages/dtschema')
print(os.pathsep.join(dict.fromkeys(paths)))
"#,
        ])
        .output()
        .expect("query Python installation paths");
    assert!(
        output.status.success(),
        "cannot query Python installation paths: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let paths = String::from_utf8(output.stdout).expect("Python installation paths are UTF-8");
    println!("cargo:rustc-env=DTSCHEMA_PACKAGE_PATHS={}", paths.trim());
}
