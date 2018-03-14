test:
	test/test-dt-validate.py

demo-good-schema:
	tools/dt-doc-validate test/schemas/good-example.yaml

demo-bad-schema:
	tools/dt-doc-validate test/schemas/bad-example.yaml

.PHONY: test demo-bad-schema demo-good-schema
