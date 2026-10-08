.PHONY: install start systemd gate test check

install:
	bash ./install.sh --skip-smoke

start:
	bash ./start.sh

systemd:
	sudo bash ./install.sh --systemd --prod --skip-smoke

gate:
	export PYTHONPATH=src:scripts; bash scripts/gate_platform_zero.sh

test:
	export PYTHONPATH=src:scripts; python3 -m pytest tests/ -q --tb=line

check:
	bash scripts/check.sh
