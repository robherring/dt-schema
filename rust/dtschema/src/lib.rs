// SPDX-License-Identifier: BSD-2-Clause
// Copyright 2026 dt-schema contributors
//! Devicetree schema validation library.
//!
//! The port keeps `serde_json::Value` as the universal representation for both
//! schema documents and decoded devicetree data.

pub mod cache;
pub mod diagnostic;
pub mod dtb;
pub mod fixups;
pub mod lib_helpers;
pub mod process;
pub mod schema;
pub mod types;
pub mod validator;
pub mod yaml;

use std::path::{Path, PathBuf};

/// Synthetic schema ID for "is this compatible documented anywhere?".
pub const GENERATED_COMPATIBLES_SCHEMA: &str = "generated-compatibles";

/// Locate the bundled `schemas/` and `meta-schemas/` data directories.
///
/// Respect `DTSCHEMA_DIR`, then look relative to the executable for pip-installed
/// data. Cargo builds fall back to the source tree's `dtschema/` directory.
pub fn bundled_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("DTSCHEMA_DIR") {
        return PathBuf::from(dir);
    }
    if let Ok(executable) = std::env::current_exe()
        && let Some(dir) = installed_dir(
            &executable,
            option_env!("DTSCHEMA_PACKAGE_PATHS").unwrap_or_default(),
        )
    {
        return dir;
    }
    // rust/dtschema/src/lib.rs -> repo/dtschema
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest
        .parent() // rust/
        .and_then(|p| p.parent()) // repo/
        .map(|p| p.join("dtschema"))
        .unwrap_or_else(|| PathBuf::from("dtschema"))
}

fn installed_dir(executable: &Path, package_paths: &str) -> Option<PathBuf> {
    let bin = executable.parent()?;
    let prefix = bin.parent()?;
    // pip --target puts the package alongside bin/.
    let mut candidates = vec![prefix.join("dtschema")];
    candidates.extend(std::env::split_paths(package_paths).map(|relative| bin.join(relative)));
    candidates
        .into_iter()
        .find(|dir| dir.join("schemas").is_dir() && dir.join("meta-schemas").is_dir())
        .and_then(|dir| dir.canonicalize().ok())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn installed_data_follows_executable_location() {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("dtschema-paths-{}-{nonce}", std::process::id()));
        for (name, data, binary, relative) in [
            ("target", "dtschema", "bin/dt-validate", ""),
            (
                "venv",
                "lib/python3.13/site-packages/dtschema",
                "bin/dt-validate",
                "../lib/python3.13/site-packages/dtschema",
            ),
        ] {
            let prefix = root.join(name);
            let package = prefix.join(data);
            std::fs::create_dir_all(prefix.join(binary).parent().unwrap()).unwrap();
            std::fs::create_dir_all(package.join("schemas")).unwrap();
            assert!(installed_dir(&prefix.join(binary), relative).is_none());
            std::fs::create_dir_all(package.join("meta-schemas")).unwrap();
            assert_eq!(
                installed_dir(&prefix.join(binary), relative)
                    .unwrap()
                    .canonicalize()
                    .unwrap(),
                package.canonicalize().unwrap()
            );
            let relocated = root.join(format!("moved-{name}"));
            std::fs::rename(&prefix, &relocated).unwrap();
            assert_eq!(
                installed_dir(&relocated.join(binary), relative)
                    .unwrap()
                    .canonicalize()
                    .unwrap(),
                relocated.join(data).canonicalize().unwrap()
            );
        }
        std::fs::remove_dir_all(root).unwrap();
    }
}

/// The dtschema version string used as a processed-schema cache key.
///
/// A processed schema's `version` field must match to be reused, so read the
/// generated version module when present to keep processed schemas
/// interchangeable with the installed tools. Falls back to the crate version.
pub fn version() -> String {
    let vpy = bundled_dir().join("version.py");
    if let Ok(text) = std::fs::read_to_string(&vpy) {
        for line in text.lines() {
            let line = line.trim_start();
            if line.starts_with("__version__") && line.contains('=') {
                if let Some(start) = line.find('\'')
                    && let Some(end) = line[start + 1..].find('\'')
                {
                    return line[start + 1..start + 1 + end].to_string();
                }
                if let Some(start) = line.find('"')
                    && let Some(end) = line[start + 1..].find('"')
                {
                    return line[start + 1..start + 1 + end].to_string();
                }
            }
        }
    }
    env!("CARGO_PKG_VERSION").to_string()
}
