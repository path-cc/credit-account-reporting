from elasticsearch.helpers import scan
from datetime import datetime
from functools import lru_cache


def query_charges(
    es_client, start_date, end_date, account=None, index="cas-daily-charge-records-*"
):
    """Returns iterator of charges given a time range"""

    query = {"index": index, "scroll": "30s", "size": 1000, "body": {}}

    query["body"]["query"] = {
        "bool": {
            "filter": [
                {"range": {"date": {"gte": str(start_date), "lt": str(end_date)}}}
            ]
        }
    }

    if account is not None:
        query["body"]["query"]["bool"]["filter"].append(
            {"term": {"account_id": account}}
        )

    for doc in scan(client=es_client, query=query.pop("body"), **query):
        yield doc


def query_usage(es_client, start_date, end_date, match_terms={}, index="path-schedd-*"):
    """Returns iterator of usage given an account and a time range"""

    # Convert date objects to timestamps
    date2ts = lambda d: int(datetime(d.year, d.month, d.day).timestamp())
    start_ts = date2ts(start_date)
    end_ts = date2ts(end_date)

    query = {"index": index, "scroll": "30s", "size": 1000, "body": {}}

    query["body"]["query"] = {
        "bool": {
            "filter": [
                {"range": {"RecordTime": {"gte": start_ts, "lt": end_ts}}},
            ]
        }
    }

    for attr, value in match_terms.items():
        query["body"]["query"]["bool"]["filter"].append({"match_phrase": {attr: value}})

    for doc in scan(client=es_client, query=query.pop("body"), **query):
        yield doc


def get_charge_data(
    es_client,
    start_date,
    end_date,
    account=None,
    addl_cols=[],
    charge_index="cas-daily-charge-records-*",
    account_index="cas-credit-accounts",
):
    """Returns rows of account data"""

    rows = []
    for charge_info in query_charges(
        es_client, start_date, end_date, account=account, index=charge_index
    ):
        row = charge_info["_source"]

        for col in addl_cols:
            # Do some column common calculations if add_cols is set
            # (But we don't have any yet)
            raise ValueError(f"Unknown additional column '{column}'")

        # Add charge_type and charge_function to all returns
        if row.get("cas_version", "v1") == "v1":
            v1_charge_function = get_v1_charge_function(
                es_client, row["account_id"], account_index
            )
            v1_type = v1_charge_function[0:3]
            row["charge_type"] = v1_type
            row["charge_function"] = v1_charge_function
            row["cas_version"] = "v1"

        rows.append(row)

    return rows


def get_usage_data(
    es_client, start_date, end_date, match_terms={}, addl_cols=[], index="path-schedd-*"
):
    """Returns rows of usage data"""

    default_cols = [
        "Owner",
        "ScheddName",
        "GlobalJobId",
        "RecordTime",
        "RemoteWallClockTime",
        "RequestCpus",
        "CpusProvisioned",
        "RequestMemory",
        "MemoryProvisioned",
        "RequestGpus",
        "GpusProvisioned",
        "MachineAttrGLIDEIN_ResourceName0",
        "JobUniverse",
    ]
    cols = default_cols + addl_cols

    rows = []
    for usage_info in query_usage(
        es_client, start_date, end_date, match_terms=match_terms, index=index
    ):
        row_in = usage_info["_source"]
        row_out = {}

        for col in cols:
            try:
                row_out[col] = row_in[col]
            except KeyError:
                row_out[col] = None

        rows.append(row_out)

    return rows


def query_account(es_client, account=None, index="cas-credit-accounts"):
    """Returns account(s) info"""

    query = {"index": index, "size": 1000, "body": {}}

    if account is not None:
        query["body"]["query"] = {"term": {"account_id": account}}

    result = es_client.search(**query)
    return result


def get_account_data(
    es_client, account=None, addl_cols=[], index="cas-credit-accounts"
):
    """Returns rows of account data"""

    rows = []
    for account_info in query_account(es_client, account=account, index=index)["hits"][
        "hits"
    ]:
        row = account_info["_source"]

        for col in addl_cols:
            # Do some column common calculations if add_cols is set
            if col == "remaining_cpu_credits":
                row[col] = row["cpu_credits"] - row.get("cpu_charges", 0)
            elif col == "remaining_gpu_credits":
                row[col] = row["gpu_credits"] - row.get("gpu_charges", 0)
            elif col == "percent_cpu_credits_used":
                if row["cpu_credits"] > 1e-8:
                    row[col] = row.get("cpu_charges", 0) / row["cpu_credits"]
                else:
                    row[col] = 0.0
            elif col == "percent_gpu_credits_used":
                if row["gpu_credits"] > 1e-8:
                    row[col] = row.get("gpu_charges", 0) / row["gpu_credits"]
                else:
                    row[col] = 0.0
            else:
                raise ValueError(f"Unknown additional column '{column}'")

        rows.append(row)

    return rows


def get_account_emails(es_client, active_since=None, index="cas-credit-accounts"):
    """Returns account ids (active since a given date)"""

    query = {"index": index, "size": 1000, "body": {}}
    if active_since is not None:
        query["body"]["query"] = {
            "bool": {
                "should": [
                    {"range": {"cpu_last_charge_date": {"gte": str(active_since)}}},
                    {"range": {"gpu_last_charge_date": {"gte": str(active_since)}}},
                ],
                "minimum_should_match": 1,
            }
        }

    active_accounts = {}
    for result in es_client.search(**query)["hits"]["hits"]:
        active_accounts[result["_source"]["account_id"]] = result["_source"][
            "owner_email"
        ]

    return active_accounts


@lru_cache(maxsize=1024)
def get_v1_charge_function(es_client, account, index="cas-credit-accounts"):
    """Returns v1 charge function given an account"""

    query = {"index": index, "size": 1000, "body": {}}
    query["body"]["query"] = {"term": {"account_id": account}}

    for result in es_client.search(**query)["hits"]["hits"]:
        v1_charge_function = result["_source"]["v1_charge_function"]
    return v1_charge_function
