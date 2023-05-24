from cas_admin.connect import connect
from datetime import date

CHARGE_ALIAS = "cas-daily-charge-records"

CLONE_PREFIX = f"backup-{date.today()}"


def clone_index(es, index, prefix):
    target_index = f"{prefix}-{index}"
    es.indices.put_settings(
        index=index,
        body={"index.blocks.read_only": True},
    )
    es.indices.clone(
        index=index,
        target=target_index,
        body={
            "settings": {
                "index.number_of_replicas": 0,
                "index.blocks.read_only": False,
            }
        },
        wait_for_active_shards=1,
    )
    es.indices.put_settings(
        index=index,
        body={"index.blocks.read_only": False},
    )
    return target_index


def main():
    es = connect()

    daily_charge_indices = list(es.indices.get_alias(index=CHARGE_ALIAS).keys())
    for daily_charge_index in daily_charge_indices:
        # 1. Clone daily charge records
        # Note that cloning will remove aliases automatically, yay!
        cloned_index = clone_index(es, daily_charge_index, CLONE_PREFIX)
        print(f"Copied {daily_charge_index} to {cloned_index}")

        # 2. Remove lifecycle policies from cloned daily charge records
        es.ilm.remove_policy(index=cloned_index)
        print(f"Removed ILM policy on {cloned_index}")


if __name__ == "__main__":
    main()
