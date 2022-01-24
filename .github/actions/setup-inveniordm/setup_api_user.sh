#!/usr/bin/env bash
# Creates a test user and obtains an API token

# test user e-mail and password required as argument
USER=$1
PASS=$2

# get the right container
RDM_NAME=inveniordm-test
CONTAINER="$(docker ps | grep "${RDM_NAME}_web-api" | awk '{print $1}')"
INVENIO="docker exec $CONTAINER invenio"

# create test user and get an API token
$INVENIO users create $USER "--password=$PASS" --active 1>&2
$INVENIO roles add $USER admin 1>&2
TOKEN=$($INVENIO tokens create -n testing-token -u $USER) 1>&2

# save info in environment variables
echo "INVENIORDM_URL=https://127.0.0.1"
echo "INVENIORDM_TOKEN=$TOKEN"
