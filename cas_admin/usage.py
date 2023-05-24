import click
import sys
from datetime import timedelta
from collections import OrderedDict
from operator import itemgetter
from elasticsearch.helpers import bulk

from cas_admin.query_utils import (
    get_account_data,
    get_charge_data,
    get_usage_data,
)
import cas_admin.cost_functions as cost_functions


def display_charges(
    es_client,
    start_date,
    end_date,
    account=None,
    collapse_users=False,
    collapse_resources=False,
    charge_index="cas-daily-charge-records-*",
    account_index="cas-credit-accounts",
):
    """Displays charges given a time range"""

    columns = OrderedDict()
    columns["date"] = "Date"
    columns["account_id"] = "Account"
    if not collapse_users:
        columns["user_id"] = "User"
    columns["charge_type"] = "JobType"
    if not collapse_resources:
        columns["resource_name"] = "Resource"
    columns["total_charges"] = "Charge"

    charge_data = get_charge_data(
        es_client,
        start_date,
        end_date,
        account=account,
        charge_index=charge_index,
        account_index=account_index,
    )
    if len(charge_data) == 0:
        click.echo(f"No charge records found.", err=True)
        sys.exit(1)
    charge_data.sort(
        key=itemgetter("date", "account_id", "user_id", "charge_type", "resource_name")
    )

    if collapse_resources:
        new_charge_data = []
        last_key = None
        total_charges = 0.0
        for charge_info in charge_data:
            key = {
                "date": charge_info["date"],
                "account_id": charge_info["account_id"],
                "user_id": charge_info["user_id"],
                "charge_type": charge_info["charge_type"],
            }
            if not last_key:
                last_key = key.copy()
            if key != last_key:
                last_key["resource_name"] = "total"
                last_key["total_charges"] = total_charges
                new_charge_data.append(last_key)
                last_key = key
                total_charges = 0.0
            total_charges += charge_info["total_charges"]
        last_key["resource_name"] = "total"
        last_key["total_charges"] = total_charges
        new_charge_data.append(last_key)
        charge_data = new_charge_data

    if collapse_users:
        charge_data.sort(
            key=itemgetter("date", "account_id", "charge_type", "resource_name")
        )
        new_charge_data = []
        last_key = None
        total_charges = 0.0
        for charge_info in charge_data:
            key = {
                "date": charge_info["date"],
                "account_id": charge_info["account_id"],
                "charge_type": charge_info["charge_type"],
                "resource_name": charge_info["resource_name"],
            }
            if not last_key:
                last_key = key.copy()
            if key != last_key:
                last_key["user_id"] = "total"
                last_key["total_charges"] = total_charges
                new_charge_data.append(last_key)
                last_key = key
                total_charges = 0.0
            total_charges += charge_info["total_charges"]
        last_key["user_id"] = "total"
        last_key["total_charges"] = total_charges
        new_charge_data.append(last_key)
        charge_data = new_charge_data

    # Set col formats
    col_format = {col: "" for col in columns}
    for col in ["total_charges"]:
        col_format[col] = ",.1f"

    # Get col sizes
    col_size = {col: len(col_name) for col, col_name in columns.items()}
    for row in charge_data:
        for col in columns:
            col_size[col] = max(col_size[col], len(f"{row.get(col, ''):{col_format[col] if col in row else ''}}"))

    # Print cols
    items = []
    for col, col_name in columns.items():
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
            if col in {"total_charges"}:
                val = row.get(col, 0)
                val = f"{val:{col_format[col]}}".rjust(col_size[col])
            else:
                val = row.get(col, "")
                val = f"{val:{col_format[col]}}".ljust(col_size[col])
            items.append(val)
        click.echo(" ".join(items))


def get_job_type(job):
    try:
        if job.get("RequestGpus") > 0:
            return "gpu"
    except Exception:
        pass
    return "cpu"


def compute_daily_charges(
    es_client,
    date,
    account_index="cas-credit-accounts",
    usage_index="path-schedd-*",
    charge_index="cas-daily-charge-records",
    account_name_attr="ProjectName",
    dry_run=False,
):
    """Computes charges given a time range"""

    account_data = get_account_data(es_client, index=account_index)

    if len(account_data) == 0:
        click.echo(f"ERROR: No accounts found in index '{account_index}'", err=True)
        sys.exit(1)

    for account_info in account_data:
        account = account_info["account_id"]
        cost_funcname = {
            "cpu": account_info["cpu_charge_function"],
            "gpu": account_info["gpu_charge_function"],
        }
        account_charges = {
            "cpu": {},
            "gpu": {},
        }

        match_terms = {account_name_attr: account}
        for usage_row in get_usage_data(
            es_client,
            date,
            date + timedelta(days=1),
            match_terms=match_terms,
            index=usage_index,
        ):
            job_type = get_job_type(usage_row)
            cost_function = getattr(cost_functions, cost_funcname[job_type])

            user = f"{usage_row.get('Owner', 'UNKNOWN')}@{usage_row.get('ScheddName', 'UNKNOWN')}"
            user_charges = account_charges[job_type].get(user, {})

            resource_charges = cost_function(usage_row)
            for resource_name, resource_charge in resource_charges.items():
                if resource_charge < 0:
                    click.echo(
                        f"WARNING: Negative cost computed for account {account} with usage from following job ad, ignoring:\n{usage_row}",
                        err=True,
                    )
                user_charges[resource_name] = (
                    user_charges.get(resource_name, 0.0) + resource_charge
                )
            account_charges[job_type][user] = user_charges

        # Create charge docs
        account_charge_docs = []
        for job_type in ["cpu", "gpu"]:
            for user, user_charges in account_charges[job_type].items():
                for resource_name, resource_charge in user_charges.items():
                    doc_source = {
                        "account_id": account,
                        "charge_type": job_type,
                        "charge_function": cost_funcname[job_type],
                        "date": str(date),
                        "user_id": user,
                        "resource_name": resource_name,
                        "total_charges": resource_charge,
                        "cas_version": "v2",
                    }
                    doc_id = f"{account}#{date}#{user}#{job_type}#{resource_name}"
                    account_charge_docs.append(
                        {"_index": charge_index, "_id": doc_id, "_source": doc_source}
                    )

        # Upload charges
        if not dry_run:
            success_count, error_infos = bulk(
                es_client, account_charge_docs, raise_on_error=False, refresh="wait_for"
            )
            if len(error_infos) > 0:
                click.echo(
                    f"Failed to add {len(error_infos)} charges in index '{charge_index}' for account {account}:",
                    err=True,
                )
                for i, error_info in enumerate(error_infos, start=1):
                    click.echo(f"\t{i}. {error_info}", err=True)
        else:
            click.echo(
                f"Dry run, not indexing {len(account_charge_docs)} new charges for account {account}."
            )


def apply_daily_charges(
    es_client,
    date,
    account_index="cas-credit-accounts",
    charge_index="cas-daily-charge-records",
    dry_run=False,
):
    """Applies daily charges to credit accounts."""

    updated_account_docs = {}

    # Load current account data
    account_infos = {}
    for account_info in get_account_data(es_client, index=account_index):
        account_infos[account_info["account_id"]] = account_info

    charge_data = get_charge_data(
        es_client,
        date,
        date + timedelta(days=1),
        charge_index=charge_index,
        account_index=account_index,
    )

    updated_accounts = {}
    for charge_info in charge_data:
        account = charge_info["account_id"]
        charge_type = charge_info["charge_type"]
        if account not in account_infos:
            click.echo(
                f"WARNING: No account '{account}' found in index '{account_index}', skipping applying charges",
                err=True,
            )
            continue

        if account not in updated_accounts:
            updated_accounts[account] = account_infos[account]

        updated_accounts[account][f"{charge_type}_charges"] += charge_info[
            "total_charges"
        ]
        updated_accounts[account][f"{charge_type}_last_charge_date"] = str(date)

    updated_account_docs = []
    for account, updated_account in updated_accounts.items():
        doc_id = account
        updated_account_docs.append(
            {"_index": account_index, "_id": doc_id, "_source": updated_account}
        )

    # Do a bulk upload.
    if not dry_run:
        success_count, error_infos = bulk(
            es_client, updated_account_docs, raise_on_error=False, refresh="wait_for"
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
