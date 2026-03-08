.PHONY: up down test makemigrations migrate createsuperuser

up:
	docker-compose up --build

down:
	docker-compose down -v

test:
	docker-compose run --rm web pytest -q

makemigrations:
	docker-compose run --rm web python manage.py makemigrations

migrate:
	docker-compose run --rm web python manage.py migrate

createsuperuser:
	docker-compose run --rm web python manage.py createsuperuser
