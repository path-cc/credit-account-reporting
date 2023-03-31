from cas_admin.connect import connect

DRY_RUN = True

ACCOUNT_INDEX = "cas-credit-accounts"

CHARGE_TEMPLATE = "cas_daily_charge_records"
CHARGE_ALIAS = "cas-daily-charge-records"

ILM_POLICY = "cas-daily-charge-records-ilm"

CLONE_PREFIX = "dev"


def remove_existing_clones(es, alias, prefix, dry_run=False):
    target = f"{prefix}-{alias}-*"
    indices = es.indices.get_alias(index=target, allow_no_indices=True)
    indices = list(indices.keys())
    indices.sort(reverse=True)
    if not dry_run and len(indices) > 0:
        es.indices.delete(index=indices, allow_no_indices=True)
    print(f"Removed {len(indices)} existing indices matching {target}")


def clone_and_fix_template(es, template, prefix, ilm_policy, alias, dry_run=False):
    target = f"{prefix}_{template}"
    target_alias = f"{prefix}-{alias}"
    body = es.indices.get_index_template(name=template)["index_templates"][0][
        "index_template"
    ]
    body["index_patterns"] = f"{target_alias}-*"
    body["template"]["settings"]["index"]["lifecycle"]["name"] = ilm_policy
    body["template"]["settings"]["index"]["lifecycle"]["rollover_alias"] = target_alias
    if not dry_run:
        if es.indices.exists_index_template(name=target):
            es.indices.delete_index_template(name=target)
        es.indices.put_index_template(name=target, body=body)
    print(f"Cloned and fixed index template {template} to {target}")


def clone_index(es, index, prefix, dry_run=False):
    target = f"{prefix}-{index}"
    es.indices.put_settings(
        index=index,
        body={"index.blocks.read_only": True},
    )
    if not dry_run:
        try:
            if es.indices.exists(index=target):
                es.indices.delete(index=target)
                print(f"Removed existing index {target}")
            es.indices.clone(
                index=index,
                target=target,
                body={
                    "settings": {
                        "index.number_of_replicas": 0,
                        "index.blocks.read_only": False,
                    }
                },
                wait_for_active_shards=1,
            )
        except Exception as e:
            print(f"Got exception {e} while trying to clone {index} to {target}")
    es.indices.put_settings(
        index=index,
        body={"index.blocks.read_only": False},
    )
    print(f"Cloned index {index} to {target}")


def add_aliases(es, indices, alias, prefix, dry_run=False):
    target_indices = [f"{prefix}-{index}" for index in indices]
    target_alias = f"{prefix}-{alias}"
    if not dry_run:
        es.indices.put_alias(
            index=target_indices[:-1], name=target_alias, body={"is_write_index": False}
        )
        es.indices.put_alias(
            index=target_indices[-1], name=target_alias, body={"is_write_index": True}
        )
    print(f"Added alias {target_alias} to cloned indices")


def main():
    es = connect()

    # 1. Remove existing indices
    remove_existing_clones(es, CHARGE_ALIAS, CLONE_PREFIX, dry_run=DRY_RUN)

    # 2. Clone index template and fix for dev
    clone_and_fix_template(
        es, CHARGE_TEMPLATE, CLONE_PREFIX, ILM_POLICY, CHARGE_ALIAS, dry_run=DRY_RUN
    )

    # 3. Clone credit accounts index
    clone_index(es, ACCOUNT_INDEX, CLONE_PREFIX, dry_run=DRY_RUN)

    # 4. Clone daily charge records
    daily_charge_indices = list(es.indices.get_alias(CHARGE_ALIAS).keys())
    daily_charge_indices.sort()
    for daily_charge_index in daily_charge_indices:
        clone_index(es, daily_charge_index, CLONE_PREFIX, dry_run=DRY_RUN)

    # 5. Add aliases
    add_aliases(es, daily_charge_indices, CHARGE_ALIAS, CLONE_PREFIX, dry_run=DRY_RUN)


if __name__ == "__main__":
    main()
