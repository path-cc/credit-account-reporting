#!/bin/bash
# Set ES_HOST to your Elasticsearch instance:
# ES_HOST=https://localhost:9200 ./push_templates_to_elasticsearch.sh

set -eux

# Push ILM policies
for ilm_policy in cas-daily-charge-records-ilm; do
    curl -XPUT "${ES_HOST}/_ilm/policy/${ilm_policy}" -H "Content-Type: application/json" -d @ilm_policies/${ilm_policy}.json
    echo
done

# Push index templates
for index_template in cas_daily_charge_records; do
    curl -XPUT "${ES_HOST}/_index_template/${index_template}" -H "Content-Type: application/json" -d @index_templates/${index_template}.json
    echo
done

# Push indices
for index in cas-users cas-credit-accounts cas-daily-charge-records-000001; do
    curl -XPUT "${ES_HOST}/${index}" -H "Content-Type: application/json" -d @indices/${index}.json
    echo
done
