.PHONY: dev test lint clean docker

dev:
	uvicorn engine.server:app --reload --port 8000

test:
	pytest tests/ -v

lint:
	ruff check engine/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache coverage htmlcov

docker:
	docker-compose up --build
