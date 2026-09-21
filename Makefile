.PHONY: test api web up down

test:
	python -m pytest

api:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd frontend && npm run dev

up:
	docker compose up --build

down:
	docker compose down
