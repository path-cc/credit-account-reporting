from elasticsearch.helpers import scan


def query_charges(
    es_client, start_ts, end_ts, account=None, index="cas-daily-charge-records-*"
):
    """Returns iterator of charges given a time range"""

    query = {"index": index, "scroll": "30s", "size": 1000, "body": {}}

    query["body"]["query"] = {
        "bool": {"filter": [{"range": {"date": {"gte": start_ts, "lt": end_ts}}}]}
    }

    if account is not None:
        query["body"]["query"]["bool"]["filter"].append(
            {"term": {"account_id": account}}
        )

    for doc in scan(client=es_client, query=query.pop("body"), **query):
        yield doc


def query_usage(es_client, start_ts, end_ts, match_terms={}, index="osg-schedd-*"):
    """Returns iterator of usage given an account and a time range"""

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
    es_client, start_ts, end_ts, account=None, addl_cols=[], index="cas-credit-accounts"
):
    """Returns rows of account data"""

    rows = []
    for charge_info in query_charges(
        es_client, start_ts, end_ts, account=account, index=index
    ):
        row = account_info["_source"]

        for col in addl_cols:
            # Do some column common calculations if add_cols is set
            # (But we don't have any yet)
            raise ValueError(f"Unknown additional column '{column}'")

        rows.append(row)

    return rows


def get_usage_data(
    es_client, start_ts, end_ts, match_terms={}, addl_cols=[], index="osg-schedd-*"
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
    for charge_info in query_usage(es_client, start_ts, end_ts, user=user, index=index):
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
