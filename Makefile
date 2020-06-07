.PHONY: docs lint test

docs:
	@$(MAKE) -C docs/ html

lint:
	flake8 .

test:
	cd test/ && python3 -m unittest discover -p "*Test.py" -v
	# @$(MAKE) -C examples python3 lechuck.py
