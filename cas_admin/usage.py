import click
import sys
from collections import OrderedDict
from operator import itemgetter
from elasticsearch.helpers import scan

from cas_admin.query_utils import get_account_data, get_charge_data, get_usage_data
import cas_admin.cost_functions as cost_functions


def display_charges(
    es_client, start_ts, end_ts, account=None, index="cas-daily-charge-records-*"
):
    """Displays charges given a time range"""

    columns = OrderedDict()
    columns["date"] = "Date"
    columns["account_id"] = "Account"
    columns["total_charges"] = "Charge"
    columns["resource_name"] = "Resource"

    charge_data = get_charge_data(
        es_client, start_ts, end_ts, account=account, index=index
    )
    if len(charge_data) == 0:
        click.echo(f"ERROR: No charge records found in index '{index}'", err=True)
        sys.exit(1)
    charge_data.sort(key=itemgetter("date", "account_id"))

    # Set col formats
    col_format = {col: "" for col in columns}
    for col in ["total_charges"]:
        col_format[col] = ",.1f"

    # Get col sizes
    col_size = {col: len(col_name) for col, col_name in columns.items()}
    for row in charge_data:
        for col in columns:
            col_size[col] = max(col_size[col], len(f"{row[col]:{col_format[col]}}"))

    # Print cols
    for col, col_name in columns.items():
        items = []
        val = col_name
        if col in {"total_charges"}:
            val = f"{val}".rjust(col_size[col])
        else:
            val = f"{val}".ljust(col_size[col])
        items.append(val)
    click.echo(" ".join(items))
    for row in charge_data:
        items = []
        for col in columns:
            val = charge_data[col]
            if col in {"total_charges"}:
                val = f"{val:{col_format[col]}}".rjust(col_size[col])
            else:
                val = f"{val:{col_format[col]}}".ljust(col_size[col])
            items.append(val)
        click.echo(" ".join(items))


def compute_charges(
    es_client,
    start_ts,
    end_ts,
    account=None,
    account_index="cas-credit-accounts",
    usage_index="osg-schedd-*",
    charge_index="cas-daily-charge-records",
    resource_name_attr="MachineAttrGLIDEIN_ResourceName0",
    dry_run=False,
):
    """Computes charges given a time range"""

    account_rows = get_account_data(es_client, index=account_index)

    if len(account_rows) == 0:
        click.echo(
            f"ERROR: No account '{account}' found in index '{account_index}'", err=True
        )
        sys.exit(1)

    for account_row in account_rows:
        cost_function = getattr(cost_functions, account_row["type"])
        charge = 0.0

        match_terms = {"CreditAccount": account_row["account_id"]}
        for usage_row in get_usage_data(
            es_client, start_ts, end_ts, match_terms=match_terms, index=usage_index
        ):
            this_charge = cost_function(usage_row)
            if this_charge < 0:
                click.echo(
                    f"WARNING: Negative cost computed for account {account} with usage from doc id {job['_id']}, ignoring",
                    err=True,
                )
                continue
            charge += this_charge

        # Skip if no charges this day
        if charge < 1e-8:
            continue

        # Create account obj
        charge_doc = {
            "account_id": account_row["account_id"],
            "date": start_ts,
            "resource_name": usage_row[resource_name_attr],
            "total_charges": cost,
        }
        doc_id = f"{account_row['account_id']}#{start_ts}"

        # Upload account
        if not dry_run:
            es_client.index(index=charge_index, id=doc_id, body=charge_doc)
