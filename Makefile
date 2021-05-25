all:
	noop

coverage:
	coverage erase
	COVERAGE_FILE="$(shell pwd)/.coverage" pytest --cov openttd_protocol
	coverage report -m
	coverage html

test:
	pytest openttd_protocol


.PHONY: all coverage test
