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
	./dt-validate.py test/juno.cpp.yaml

validate-%:
	./dt-validate.py ../devicetree-rebasing/src/$*

validate-all:
	./dt-validate.py ../devicetree-rebasing/src

.PHONY: test demo-bad-schema demo-good-schema demo-validate validate-all
