# SPDX-License-Identifier: BSD-2-Clause
# Copyright 2018 Linaro Ltd.
# Copyright 2018 Arm Ltd.
test:
	test/test-dt-validate.py

demo-good-schema:
	tools/dt-doc-validate test/schemas/good-example.yaml

demo-bad-schema:
	tools/dt-doc-validate test/schemas/bad-example.yaml

demo-validate:
	tools/dt-validate test/juno.cpp.yaml

validate-%:
	tools/dt-validate ../devicetree-rebasing/src/$*

validate-all:
	tools/dt-validate ../devicetree-rebasing/src

.PHONY: test demo-bad-schema demo-good-schema demo-validate validate-all
