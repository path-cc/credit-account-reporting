import click
import sys
from datetime import timedelta
from collections import OrderedDict
from operator import itemgetter
from elasticsearch.helpers import scan, bulk

from cas_admin.query_utils import (
    get_account_data,
    get_charge_data,
    get_usage_data,
    query_account,
)
import cas_admin.cost_functions as cost_functions


def display_charges(
    es_client, start_date, end_date, account=None, index="cas-daily-charge-records-*"
):
    """Displays charges given a time range"""

    columns = OrderedDict()
    columns["date"] = "Date"
    columns["account_id"] = "Account"
    columns["total_charges"] = "Charge"
    columns["resource_name"] = "Resource"

    charge_data = get_charge_data(
        es_client, start_date, end_date, account=account, index=index
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


def compute_daily_charges(
    es_client,
    date,
    account_index="cas-credit-accounts",
    usage_index="osg-schedd-*",
    charge_index="cas-daily-charge-records",
    resource_name_attr="MachineAttrGLIDEIN_ResourceName0",
    account_name_attr="ProjectName",
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

        match_terms = {account_name_attr: account_row["account_id"]}
        for usage_row in get_usage_data(
            es_client,
            date,
            date + timedelta(days=1),
            match_terms=match_terms,
            index=usage_index,
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

        # Create charge doc
        charge_doc = {
            "account_id": account_row["account_id"],
            "date": str(date),
            "resource_name": usage_row[resource_name_attr],
            "total_charges": cost,
        }
        doc_id = f"{account_row['account_id']}#{date}"

        # Upload charge
        if not dry_run:
            es_client.index(index=charge_index, id=doc_id, body=charge_doc)
        else:
            click.echo(f"Dry run, not indexing doc with id '{doc_id}'")


def apply_daily_charges(
    es_client,
    date,
    account_index="cas-credit-accounts",
    charge_index="cas-daily-charge-records",
    dry_run=False,
):
    """Applies daily charges to credit accounts."""

    updated_account_docs = []

    for charge_info in get_charge_data(
        es_client, date, date + timedelta(days=1), account=None, index=charge_index
    ):
        old_account_info = query_account(
            es_client, account=charge_info["account_id"], index=account_index
        )["hits"]["hits"]

        if len(old_account_info) == 0:
            click.echo(
                f"WARNING: No account '{account}' found in index '{account_index}', skipping applying charges",
                err=True,
            )
            continue
        elif len(account_info) > 1:
            click.echo(
                f"WARNING: Found multiple accounts named '{account}' in index '{account_index}', skipping applying charges",
                err=True,
            )
        old_account_doc = old_account_info[0]

        updated_account_doc = {
            "_index": account_index,
            "_id": old_account_doc["_id"],
            "_source": old_account_doc["_source"],
        }

        updated_account_doc["_source"]["total_charges"] += charge_info["total_charges"]
        updated_account_doc["_source"]["last_charge_date"] = str(date)

        updated_account_docs.append(updated_account_doc)

    # Do a bulk upload.
    # Note that this is *not* transactional. Elasticsearch by definition does not do transactions.
    if not dry_run:
        success_count, error_infos = bulk(
            es_client, updated_account_docs, raise_on_error=False
        )
        if len(error_infos) > 0:
            click.echo(
                f"Failed to update {len(error_infos)} accounts in index '{account_index}':",
                err=True,
            )
            for i, error_info in enumerate(error_infos, start=1):
                click.echo(f"\t{i}. {error_info}", err=True)
    else:
        click.echo(
            f"Dry run, not indexing {len(updated_account_docs)} updated accounts."
        )
