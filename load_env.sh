#!/bin/bash
# Load .env file into current shell environment

if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "Loaded environment variables from .env"
else
    echo ".env file not found"
fi

