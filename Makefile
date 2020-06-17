export PYTHONPATH=$PWD
include .env

db_init:
	PGPASSWORD=postgres createuser -U postgres -h ${DB_HOST} -p ${DB_PORT} -d -l ${DB_USER}
	PGPASSWORD=postgres psql -U postgres -h ${DB_HOST} -p ${DB_PORT} \
		-c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}'"
	PGPASSWORD=postgres createdb -U postgres -h ${DB_HOST} -p ${DB_PORT} -O ${DB_USER} ${DB_NAME}

pip_deps:
	pip3 install -r requirements.txt

django_prepare:
	./manage.py migrate
	DJANGO_SUPERUSER_PASSWORD=${ADMIN_PASSWORD} ./manage.py createsuperuser --no-input --username ${ADMIN_USER} \
		--email ${ADMIN_EMAIL}


dev: db_init pip_deps django_prepare
