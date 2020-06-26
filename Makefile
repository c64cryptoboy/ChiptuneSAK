.PHONY: docs lint test clean venv

docs:
	@$(MAKE) -C docs/ html

lint:
	flake8 .

test:
	python3 -m unittest discover -p "*Test.py" -v
	# @$(MAKE) -C examples python3 lechuck.py

clean:
	git reset --hard
	git clean -fdx --exclude venv/

venv:
	python3 -m venv venv
	./venv/bin/pip install -e .
	./venv/bin/pip install -r requirements.txt
