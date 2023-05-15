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


def create_base_index(es, alias, prefix, dry_run=False):
    target_alias = f"{prefix}-{alias}"
    target_index = f"{target_alias}-000001"
    aliases = {f"{target_alias}": {"is_write_index": True}}

    if not dry_run:
        es.indices.create(index=target_index, aliases=aliases)
    print(f"Created base index {target_index} with alias {target_alias}")


def clear_account_usage(es, index, prefix, dry_run=False):
    target = f"{prefix}-{index}"
    body = {
        "script": {
            "inline": "ctx._source.cpu_charges = 0; ctx._source.gpu_charges = 0;",
            "lang": "painless",
        }
    }
    if not dry_run:
        es.update_by_query(index=target, body=body)
    print(f"Cleared usage from index {target}")


def main():
    es = connect()

    # 1. Remove existing indices
    remove_existing_clones(es, CHARGE_ALIAS, CLONE_PREFIX, dry_run=DRY_RUN)

    # 2. Clone index template and fix for dev -- not really necessary after setup
    # clone_and_fix_template(
    #    es, CHARGE_TEMPLATE, CLONE_PREFIX, ILM_POLICY, CHARGE_ALIAS, dry_run=DRY_RUN
    # )

    # 3. Create base index and alias
    create_base_index(es, CHARGE_ALIAS, CLONE_PREFIX, dry_run=DRY_RUN)

    # 4. Clear out existing credits
    clear_account_usage(es, ACCOUNT_INDEX, CLONE_PREFIX, dry_run=DRY_RUN)


if __name__ == "__main__":
    main()
