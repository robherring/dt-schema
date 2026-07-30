// SPDX-License-Identifier: BSD-2-Clause
// Copyright 2026 dt-schema contributors
//! `dt-mk-schema`: build a processed schema from raw binding YAML directories.
//!
//! Reads directories or YAML files, meta-validates and fixes up each, attaches
//! the generated type / compatible caches, and emits an indexed runtime schema
//! (`-j`) or YAML. `--legacy-json` retains the old textual representation.

use std::io::Write;
use std::path::PathBuf;

use clap::Parser;
use dtschema::process::ProcessedSchemas;

#[derive(Parser)]
#[command(name = "dt-mk-schema", about = "Build a processed devicetree schema")]
struct Args {
    /// Filename of the processed schema (default: stdout).
    #[arg(short = 'o', long = "outfile")]
    outfile: Option<PathBuf>,

    /// Emit the versioned indexed processed-schema format.
    #[arg(short = 'j', long = "json")]
    json: bool,

    /// Encode an indexed runtime schema. Schema payloads are loaded lazily by
    /// the Rust validator; this format is intentionally opaque.
    #[arg(long = "indexed")]
    indexed: bool,

    /// Emit the legacy textual JSON processed-schema format.
    #[arg(long = "legacy-json", conflicts_with_all = ["json", "indexed"])]
    legacy_json: bool,

    /// Only process user schemas (skip the bundled core schemas).
    #[arg(short = 'u', long = "useronly")]
    useronly: bool,

    /// Names of directories, or YAML encoded schema files.
    schemas: Vec<PathBuf>,

    /// Print version number.
    #[arg(short = 'V', long = "version")]
    version: bool,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse_from(argfile::expand_args(
        argfile::parse_fromfile,
        argfile::PREFIX,
    )?);

    if args.version {
        println!("{}", dtschema::version());
        return Ok(());
    }

    let ps = ProcessedSchemas::build(&args.schemas, !args.useronly, &dtschema::version());
    if ps.schemas.len() <= 1 {
        // Only the `version` marker → nothing processed.
        std::process::exit(255);
    }

    let mut out: Box<dyn Write> = match &args.outfile {
        Some(p) => Box::new(std::fs::File::create(p)?),
        None => Box::new(std::io::stdout()),
    };

    if args.json || args.indexed {
        ps.write_indexed(&mut out)?;
    } else if args.legacy_json {
        let text = serde_json::to_string_pretty(&ps.schemas)?;
        writeln!(out, "{text}")?;
    } else {
        let value = serde_json::to_value(&ps.schemas)?;
        let s = serde_yaml::to_string(&value)?;
        write!(out, "{s}")?;
    }

    Ok(())
}
