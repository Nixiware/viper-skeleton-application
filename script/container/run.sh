#!/bin/bash

# exporting all environmental variables to a file
printenv | sed 's/^\(.*\)$/export \1/g' > /root/env.sh

# waiting for MySQL to become ready
until nc -z -v -w30 $DB_HOST 3306
do
	echo "[RUN] Waiting for database connection."
	sleep 5
done

# passing to CMD
exec "$@"