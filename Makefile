.PHONY: install server call batch analyze report dashboard test lint

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	cd dashboard && npm install

server:
	uvicorn bot.server:app --host 0.0.0.0 --port 8000

call:
	python -m bot.cli call --scenario $(SCENARIO)

batch:
	python -m bot.cli run-batch

analyze:
	python -m bot.cli analyze-all

report:
	python -m bot.cli build-report

dashboard:
	cd dashboard && npm start

test:
	pytest

lint:
	ruff check bot tests
