from cas_admin.connect import connect
from pathlib import Path
from pprint import pprint
import elasticsearch
import json
import sys
import os


ACCOUNT_INDEX = os.environ.get("CAS_ACCOUNT_INDEX", "cas-credit-accounts")
CHARGE_INDEX_ILM = "cas-daily-charge-records-ilm"
CHARGE_INDEX_TEMPLATE = os.environ.get(
    "CAS_CHARGE_INDEX_TEMPLATE", "cas_daily_charge_records"
)
CHARGE_INDEX_PATTERN = os.environ.get(
    "CAS_CHARGE_INDEX_PATTERN", "cas-daily-charge-records-*"
)
CHARGE_INDEX_ALIAS = os.environ.get("CAS_CHARGE_INDEX", "cas-daily-charge-records")


ACCOUNT_INDEX_FILE = Path("indices/cas-credit-accounts.json")
CHARGE_INDEX_ILM_FILE = Path("ilm_policies/cas-daily-charge-records-ilm.json")
CHARGE_INDEX_TEMPLATE_FILE = Path("index_templates/cas_daily_charge_records.json")
CHARGE_INDEX_FILE = Path("indices/cas-daily-charge-records-000001.json")


def push_ilm_policy(es, policy_name, policy_body):
    print(f'Pushing ILM policy "{policy_name}"')
    es_ilm = elasticsearch.client.IlmClient(es)
    result = es_ilm.put_lifecycle(policy=policy_name, body=policy_body)
    pprint(result)


def push_index_template(es, template_name, template_body):
    print(f'Pushing index template "{template_name}"')
    result = es.indices.put_index_template(name=template_name, body=template_body)
    pprint(result)


def reindex(es, from_index, to_index):
    query = {"source": {"index": from_index}, "dest": {"index": to_index}}
    result = es.reindex(body=query)
    return result


def clone_index(es, from_index, to_index):
    es.indices.put_settings(
        index=from_index,
        body={"index.blocks.read_only": True},
    )
    if es.indices.exists(index=to_index):
        es.indices.delete(index=to_index)
        print(f"Removed existing index {to_index}")
    es.indices.clone(
        index=from_index,
        target=to_index,
        body={
            "settings": {
                "index.number_of_replicas": 0,
                "index.blocks.read_only": False,
            }
        },
        wait_for_active_shards=1,
    )
    es.indices.put_settings(
        index=from_index,
        body={"index.blocks.read_only": False},
    )
    print(f"Cloned index {from_index} to {to_index}")


def push_index(es, index_name, index_body):
    if es.indices.exists(index=index_name):
        if index_name.startswith("v1") or index_name.startswith("v2"):
            print("Loop detected!")
            sys.exit(1)
        new_index_name = f"v2-{index_name}"
        old_index_name = f"v1-{index_name}"

        print(
            f'Index "{index_name}" exists, attempting reindex using new index "{new_index_name}"'
        )
        push_index(es, new_index_name, index_body)
        reindex(es, from_index=index_name, to_index=new_index_name)

        print(f'Cloning from "{index_name}" to "{old_index_name}"')
        clone_index(es, index_name, old_index_name)

        print(f'Deleting original "{index_name}"')
        aliases = (
            es.indices.get_alias(index=index_name)
            .get(index_name, {})
            .get("aliases", {})
        )
        es.indices.delete(index=index_name)

        print(f'Adding alias "{index_name}" to "{new_index_name}"')
        es.indices.put_alias(index=new_index_name, name=index_name)
        for alias_name, alias_body in aliases.items():
            print(f'Adding alias "{alias_name}" to "{new_index_name}"')
            es.indices.put_alias(index=new_index_name, name=alias_name, body=alias_body)

    else:
        print(f'Index "{index_name}" does not exist, creating new index')
        result = es.indices.create(index=index_name, **index_body)


def get_writable_charge_indices(es, index_alias):
    writable_charge_indices = []
    for index_name, alias_body in es.indices.get_alias(index=index_alias).items():
        if alias_body["aliases"][index_alias]["is_write_index"]:
            writable_charge_indices.append(index_name)
    return writable_charge_indices


def main():
    es = connect()

    try:
        account_index_body = json.load(ACCOUNT_INDEX_FILE.open("r"))
        charge_index_ilm_policy_body = json.load(CHARGE_INDEX_ILM_FILE.open("r"))
        charge_index_template_body = json.load(CHARGE_INDEX_TEMPLATE_FILE.open("r"))
        charge_index_example_body = json.load(CHARGE_INDEX_FILE.open("r"))
    except IOError as e:
        print(
            f'ERROR: Could not read from "{e.filename}": "{e.strerror}"',
            file=sys.stderr,
        )
        sys.exit(1)

    # fix template pattern
    charge_index_template_body["index_patterns"] = [CHARGE_INDEX_PATTERN]

    # fix template alias
    charge_index_template_body["template"]["settings"]["index"]["lifecycle"][
        "rollover_alias"
    ] = CHARGE_INDEX_ALIAS

    # fix example charge index
    charge_index_example_body["aliases"][
        CHARGE_INDEX_ALIAS
    ] = charge_index_example_body["aliases"].pop("cas-daily-charge-records")

    push_index(es, index_name=ACCOUNT_INDEX, index_body=account_index_body)
    push_ilm_policy(
        es, policy_name=CHARGE_INDEX_ILM, policy_body=charge_index_ilm_policy_body
    )
    push_index_template(
        es,
        template_name=CHARGE_INDEX_TEMPLATE,
        template_body=charge_index_template_body,
    )

    # If charge indices exist, get the writable index and update its body with the template's body,
    # otherwise push a new seed index matching the index pattern and numbered 000001.
    try:
        writable_charge_indices = get_writable_charge_indices(
            es, index_alias=CHARGE_INDEX_ALIAS
        )
    except elasticsearch.exceptions.NotFoundError:
        charge_index = CHARGE_INDEX_PATTERN.replace("*", "000001")
        push_index(es, index_name=charge_index, index_body=charge_index_example_body)
    else:
        for charge_index in writable_charge_indices:
            push_index(
                es,
                index_name=charge_index,
                index_body=charge_index_template_body["template"],
            )


if __name__ == "__main__":
    main()
