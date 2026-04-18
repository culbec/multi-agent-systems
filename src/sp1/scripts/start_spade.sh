#!/usr/bin/sh

set +xe

# We can add more parameters here; didn't bother currently, only the DB path is of interest in order to
# ignore it from version control.
DB_PATH="$(pwd)/data/spade/server.db"

# Allows path creation by the script to ensure that, for instance, the DB is created.
ALLOW_PATH_CREATION=0

if ! [ -x "$(command -v uv)" ]; then
    printf 'Error: uv is not installed.\nInstall uv from https://docs.astral.sh/uv/'. >&2
    exit 1
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--db)
            DB_PATH=$2
            shift
            shift
            ;;
        --allow-path-creation)
            ALLOW_PATH_CREATION=1
            shift
            ;;
    esac
done

if ! [ -d $(dirname $DB_PATH) ]; then
    if [ $ALLOW_PATH_CREATION -eq 0 ]; then
        printf "Error: the DB directory for SPADE does not exist!\nYou can create it using 'mkdir -p $(dirname $DB_PATH)'" >&2
        exit 2
    else
        mkdir -p $(dirname $DB_PATH)
    fi
fi 

echo "Starting the SPADE server. Using $DB_PATH for the database path..."
uv run spade run --db $DB_PATH