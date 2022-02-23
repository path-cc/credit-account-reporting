from elasticsearch.helpers import scan
from datetime import datetime


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
    index="cas-credit-accounts",
):
    """Returns rows of account data"""

    rows = []
    for charge_info in query_charges(
        es_client, start_date, end_date, account=account, index=index
    ):
        row = account_info["_source"]

        for col in addl_cols:
            # Do some column common calculations if add_cols is set
            # (But we don't have any yet)
            raise ValueError(f"Unknown additional column '{column}'")

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
    for charge_info in query_usage(
        es_client, start_date, end_date, user=user, index=index
    ):
        row_in = account_info["_source"]
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
            if col == "remaining_credits":
                row[col] = row["total_credits"] - row["total_charges"]
            elif col == "percent_credits_used":
                row[col] = row["total_charges"] / row["total_credits"]
            else:
                raise ValueError(f"Unknown additional column '{column}'")

        rows.append(row)

    return rows


def query_user(es_client, user=None, index="cas-users"):
    """Returns user(s) info"""

    query = {"index": index, "size": 1000, "body": {}}

    if user is not None:
        query["body"]["query"] = {"term": {"user_id": user}}

    result = es_client.search(**query)
    return result


def get_user_data(es_client, user=None, index="cas-users"):
    """Returns rows of user data"""

    rows = []
    for user_info in query_user(es_client, user=user, index=index)["hits"]["hits"]:
        row = user_info["_source"]
        rows.append(row)

    return rows


def get_account_emails(es_client, active_since=None, index="cas-credit-accounts"):
    """Returns account ids (active since a given date)"""

    query = {"index": index, "size": 1000, "body": {}}
    if active_since is not None:
        query["body"]["query"] = {
            "range": {"last_charge_date": {"gte": str(active_since)}}
        }

    active_accounts = {}
    for result in es_client.search(**query)["hits"]["hits"]:
        active_accounts[result["_source"]["account_id"]] = result["_source"][
            "owner_email"
        ]

    return active_accounts
