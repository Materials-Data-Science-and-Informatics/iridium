#!/usr/bin/env bash
# It takes some time until the vocabularies and demo data
# of a default Invenio RDM instance are indexed and everything works correctly.
# This script basically just waits until demo records start to appear.
# After that, the test suite can be started against the instance.

# If an argument is passed, it is supposed to be the .env file to load
# that contains the INVENIORDM_URL and INVENIORDM_TOKEN variables.
# Otherwise, these variables are used from the Github CI environment
# (if set up correctly).
if [ -n "$1" ]; then
    source $1
fi

# takes environment variables with invenio RDM credentials, waits for demo records to appear
url="${INVENIORDM_URL}/api/records?access_token=${INVENIORDM_TOKEN}"
echo Query URL: $url

function some_other_record() {
    curl -s -k $url | jq .hits.total
}

retry=0
max_retries=50 # 20 retries empirically is not always enough. decrease on own risk.

# wait until records are found through the API or we give up
hits=$(some_other_record)
while [[ "$hits" -eq 0 ]]; do
    echo "Wait for records (attempt: $retry/$max_retries)"
    sleep 5
    hits=$(some_other_record)

    if [[ "$retry" -gt "$max_retries" ]]; then
        echo "Timeout! This takes way too long!"
        exit 1
    fi
    retry=$((retry+1))
done

echo "Success!"
