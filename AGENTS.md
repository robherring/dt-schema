# AGENTS.md

dt-schema validates Devicetree data and binding schemas. See `README.md` for
usage and `pyproject.toml` for package metadata and command definitions.

## Repository

- `dtschema/schemas/` contains core bindings; device-specific bindings live in
  the Linux kernel tree. `dtschema/meta-schemas/` validates binding documents.
- `dtschema/` contains the Python library and CLIs; `test/` contains fixtures
  and the test suite.
- Installed CLI names and options form the Linux kernel integration contract.
  Keep changes compatible with its binding and DTB validation workflows.

## Development and checks

Use a virtualenv. Tests require `dtc`; building `pylibfdt` requires `swig`.
Versioning uses setuptools-scm; do not edit generated `dtschema/version.py`.

```sh
pip install -e .
python3 test/test-dt-validate.py
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
yamllint --strict $(git ls-files '*.yaml')
```

## Editing

- Keep changes focused and follow existing style.
- Use `example-schema.yaml` as the binding template and
  `test/schemas/good-example.yaml` as a minimal valid example.
- Follow `.yamllint`: two-space indentation, `---` document start, no empty
  values, and quote property names starting with `#`. Use `tools/yaml-format`.
- Binding `$id` values must match their paths. After editing a binding, run
  `dt-doc-validate <file>` and the full Python test suite.
- Update this guide with changes that affect its instructions.

## Contributions

Follow the kernel's [AI assistance guidance](https://docs.kernel.org/process/coding-assistants.html):

- A human must review generated changes and take responsibility for correctness
  and licensing.
- Agents must not add `Signed-off-by` tags; only a human can certify the DCO.
- Add `Assisted-by: AGENT_NAME:MODEL_VERSION [TOOL1] [TOOL2]` to assisted commits.
  List specialized analysis tools, not basic tools such as git or editors.
- Use BSD-2-Clause SPDX headers on new Python/YAML files and match existing
  copyright style.
