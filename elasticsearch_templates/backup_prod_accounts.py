from cas_admin.connect import connect
from datetime import date

ACCOUNT_INDEX = "cas-credit-accounts"

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

    # 1. Clone credit accounts index
    cloned_index = clone_index(es, ACCOUNT_INDEX, CLONE_PREFIX)
    print(f"Copied {ACCOUNT_INDEX} to {cloned_index}")


if __name__ == "__main__":
    main()
