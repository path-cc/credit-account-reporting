import click
import time
import sys
from datetime import date
from collections import OrderedDict
from operator import itemgetter

from cas_admin.query_utils import query_account, get_account_data, get_charge_data
import cas_admin.cost_functions as cost_functions

# Account types must match the names of cost functions
ACCOUNT_TYPES = [x for x in dir(cost_functions) if not x.startswith("_")]


def display_account(es_client, account, index="cas-credit-accounts"):
    """Displays account info"""

    columns = OrderedDict()
    columns["account_id"] = "Account Name"
    columns["owner"] = "Owner"
    columns["owner_email"] = "Owner Email"
    columns["owner_project"] = "Owner Project"
    columns["cpu_credits"] = "CPU Credits"
    columns["cpu_charges"] = "CPU Charges"
    columns["percent_cpu_credits_used"] = "Pct CPU Credits Used"
    columns["remaining_cpu_credits"] = "CPU Credits Remaining"
    columns["gpu_credits"] = "GPU Credits"
    columns["gpu_charges"] = "GPU Charges"
    columns["percent_gpu_credits_used"] = "Pct GPU Credits Used"
    columns["remaining_gpu_credits"] = "GPU Credits Remaining"

    addl_cols = [
        "percent_cpu_credits_used",
        "remaining_cpu_credits",
        "percent_gpu_credits_used",
        "remaining_gpu_credits",
    ]

    account_data = get_account_data(
        es_client, account=account, addl_cols=addl_cols, index=index
    )

    if len(account_data) == 0:
        click.echo(f"ERROR: No account '{account}' found in index '{index}'", err=True)
        sys.exit(1)
    if len(account_data) > 1:
        click.echo(
            f"ERROR: Multiple hits found for account '{account}' in index '{index}'",
            err=True,
        )
        sys.exit(1)
    account_info = account_data[0]

    for col, col_name in columns.items():
        val = account_info.get(col, "")
        if col in {
            "cpu_credits",
            "cpu_charges",
            "remaining_cpu_credits",
            "gpu_credits",
            "gpu_charges",
            "remaining_gpu_credits",
        }:
            val = f"{val:,.2f}"
        elif col in {"percent_cpu_credits_used", "percent_gpu_credits_used"}:
            val = f"{val:.2%}"
        click.echo(f"{col_name}:\t{val}")


def display_all_accounts(
    es_client, sort_col="account_id", sort_reverse=False, index="cas-credit-accounts"
):
    """Displays all accounts info"""

    columns = OrderedDict()
    columns["account_id"] = "Name"
    columns["owner"] = "Owner"
    columns["owner_project"] = "Project"
    columns["cpu_credits"] = "CpuCredits"
    columns["cpu_charges"] = "CpuCharges"
    columns["percent_cpu_credits_used"] = "PctCpuUsed"
    columns["remaining_cpu_credits"] = "CpuRemain"
    columns["gpu_credits"] = "GpuCredits"
    columns["gpu_charges"] = "GpuCharges"
    columns["percent_gpu_credits_used"] = "PctGpuUsed"
    columns["remaining_gpu_credits"] = "GpuRemain"

    addl_cols = [
        "percent_cpu_credits_used",
        "remaining_cpu_credits",
        "percent_gpu_credits_used",
        "remaining_gpu_credits",
    ]

    account_data = get_account_data(es_client, addl_cols=addl_cols, index=index)
    if len(account_data) == 0:
        click.echo(f"ERROR: No accounts found in index '{index}'", err=True)
        sys.exit(1)
    account_data.sort(key=itemgetter(sort_col, "account_id"), reverse=sort_reverse)

    # Set col formats
    col_format = {col: "" for col in columns}
    for col in [
        "cpu_credits",
        "cpu_charges",
        "remaining_cpu_credits",
        "gpu_credits",
        "gpu_charges",
        "remaining_gpu_credits",
    ]:
        col_format[col] = ",.1f"
    for col in ["percent_cpu_credits_used", "percent_gpu_credits_used"]:
        col_format[col] = ".1%"

    # Get col sizes
    col_size = {col: len(col_name) for col, col_name in columns.items()}
    for row in account_data:
        for col in columns:
            col_size[col] = max(
                col_size[col], len(f"{row.get(col, ''):{col_format[col]}}")
            )

    # Print cols
    items = []
    for col, col_name in columns.items():
        val = col_name
        if col in {
            "cpu_credits",
            "cpu_charges",
            "remaining_cpu_credits",
            "percent_cpu_credits_used",
            "gpu_credits",
            "gpu_charges",
            "remaining_gpu_credits",
            "percent_gpu_credits_used",
        }:
            val = f"{val}".rjust(col_size[col])
        else:
            val = f"{val}".ljust(col_size[col])
        items.append(val)
    click.echo(" ".join(items))
    for row in account_data:
        items = []
        for col in columns:
            val = row.get(col, "")
            if col in {
                "cpu_credits",
                "cpu_charges",
                "remaining_cpu_credits",
                "percent_cpu_credits_used",
                "gpu_credits",
                "gpu_charges",
                "remaining_gpu_credits",
                "percent_gpu_credits_used",
            }:
                val = f"{val:{col_format[col]}}".rjust(col_size[col])
            else:
                val = f"{val:{col_format[col]}}".ljust(col_size[col])
            items.append(val)
        click.echo(" ".join(items))


def add_account(
    es_client,
    account,
    owner,
    email,
    project,
    cpu_function,
    gpu_function,
    cpu_credts=0,
    gpu_credts=0,
    index="cas-credit-accounts",
):
    """Adds account"""

    try:
        credts = float(credts)
    except ValueError:
        click.echo(f"ERROR: Non-numeric credits provided: {credts}", err=True)

    # Check existing
    if len(query_account(es_client, account=account, index=index)["hits"]["hits"]) > 0:
        click.echo(
            "ERROR: Existing account {account} already found in index {index}", err=True
        )
        sys.exit(1)

    # Create account obj
    account_info = {
        "account_id": account,
        "owner": owner,
        "owner_email": email,
        "owner_project": project,
        "cpu_charge_function": cpu_function,
        "cpu_credits": cpu_credts,
        "cpu_charges": 0,
        "cpu_last_credit_date": str(date.today()),
        "gpu_charge_function": gpu_function,
        "gpu_credits": gpu_credts,
        "gpu_charges": 0,
        "gpu_last_credit_date": str(date.today()),
        "cas_version": "v2",
    }
    doc_id = account

    # Upload account
    es_client.index(index=index, id=doc_id, body=account_info)
    click.echo(f"account {account} added.")


def edit_owner(
    es_client, account, name=None, email=None, project=None, index="cas-credit-accounts"
):
    """Modifies account owner"""

    # Check that something is being modified
    if name is None and email is None and project is None:
        click.echo(
            "ERROR: One of owner name, email, or project must be modified", err=True
        )
        sys.exit(1)

    # Check existing
    existing_account_results = query_account(es_client, account=account, index=index)
    if len(existing_account_results["hits"]["hits"]) == 0:
        click.echo("ERROR: No existing account {account} in index {index}", err=True)
        sys.exit(1)
    if len(existing_account_results["hits"]["hits"]) > 1:
        click.echo(
            "ERROR: Multiple accounts found for {account} in index {index}", err=True
        )
        sys.exit(1)

    # Update account obj
    doc_id = existing_account_results["hits"]["hits"][0]["_id"]
    account_info = existing_account_results["hits"]["hits"][0]["_source"]
    if name is not None:
        account_info["owner"] = name
    if email is not None:
        account_info["owner_email"] = email
    if project is not None:
        account_info["owner_project"] = project

    # Upload account
    es_client.index(index=index, id=doc_id, body=account_info)
    click.echo(f"Account {account} updated.")


def add_credits(es_client, account, credt_type, credts, index="cas-credit-accounts"):
    """Adds credits to account"""

    # Check input
    try:
        credts = float(credts)
    except ValueError:
        click.echo(f"Non-numeric credits provided: {credts}", err=True)
        sys.exit(1)
    if credt_type not in {"cpu", "gpu"}:
        click.echo(f"Unknown credit type {credt_type} provided", err=True)
        sys.exit(1)

    # Check existing
    existing_account_results = query_account(es_client, account=account, index=index)
    if len(existing_account_results["hits"]["hits"]) == 0:
        click.echo("ERROR: No existing account {account} in index {index}", err=True)
        sys.exit(1)
    if len(existing_account_results["hits"]["hits"]) > 1:
        click.echo(
            "ERROR: Multiple accounts found for {account} in index {index}", err=True
        )
        sys.exit(1)

    # Update account obj
    doc_id = existing_account_results["hits"]["hits"][0]["_id"]
    account_info = existing_account_results["hits"]["hits"][0]["_source"]
    account_info[f"{credt_type}_credits"] += credts
    account_info[f"{credt_type}_last_credit_date"] = str(date.today())

    # Upload account
    es_client.index(index=index, id=doc_id, body=account_info)
    click.echo(f"Account {account} updated.")


def edit_credits(es_client, account, credt_type, credts, index="cas-credit-accounts"):
    """Adds credits to account"""

    # Check input
    try:
        credts = float(credts)
    except ValueError:
        click.echo(f"Non-numeric credits provided: {credts}", err=True)
        sys.exit(1)
    if credt_type not in {"cpu", "gpu"}:
        click.echo(f"Unknown credit type {credt_type} provided", err=True)
        sys.exit(1)

    # Check existing
    existing_account_results = query_account(es_client, account=account, index=index)
    if len(existing_account_results["hits"]["hits"]) == 0:
        click.echo("ERROR: No existing account {account} in index {index}", err=True)
        sys.exit(1)
    if len(existing_account_results["hits"]["hits"]) > 1:
        click.echo(
            "ERROR: Multiple accounts found for {account} in index {index}", err=True
        )
        sys.exit(1)

    # Update account obj
    doc_id = existing_account_results["hits"]["hits"][0]["_id"]
    account_info = existing_account_results["hits"]["hits"][0]["_source"]
    account_info[f"{credt_type}_credits"] = credts
    account_info[f"{credt_type}_last_credit_date"] = str(date.today())

    # Upload account
    es_client.index(index=index, id=doc_id, body=account_info)
    click.echo(f"Account {account} updated.")


def edit_charges(es_client, account, charge_type, charges, index="cas-credit-accounts"):
    """Edits charges on account"""

    # Check input
    try:
        charges = float(charges)
    except ValueError:
        click.echo(f"Non-numeric charges provided: {charges}", err=True)
        sys.exit(1)
    if charge_type not in {"cpu", "gpu"}:
        click.echo(f"Unknown charge type {charge_type} provided", err=True)
        sys.exit(1)

    # Check existing
    existing_account_results = query_account(es_client, account=account, index=index)
    if len(existing_account_results["hits"]["hits"]) == 0:
        click.echo("ERROR: No existing account {account} in index {index}", err=True)
        sys.exit(1)
    if len(existing_account_results["hits"]["hits"]) > 1:
        click.echo(
            "ERROR: Multiple accounts found for {account} in index {index}", err=True
        )
        sys.exit(1)

    # Update account obj
    doc_id = existing_account_results["hits"]["hits"][0]["_id"]
    account_info = existing_account_results["hits"]["hits"][0]["_source"]
    account_info[f"{charge_type}_charges"] = charges

    # Upload account
    es_client.index(index=index, id=doc_id, body=account_info)
    click.echo(f"Account {account} updated.")


def add_charges(es_client, account, charge_type, charges, index="cas-credit-accounts"):
    """Adds charges to account"""

    # Check input
    try:
        charges = float(charges)
    except ValueError:
        click.echo(f"Non-numeric charges provided: {charges}", err=True)
        sys.exit(1)
    if charge_type not in {"cpu", "gpu"}:
        click.echo(f"Unknown charge type {charge_type} provided", err=True)
        sys.exit(1)

    # Check existing
    existing_account_results = query_account(es_client, account=account, index=index)
    if len(existing_account_results["hits"]["hits"]) == 0:
        click.echo(
            "ERROR: No existing account '{account}' in index '{index}'", err=True
        )
        sys.exit(1)
    if len(existing_account_results["hits"]["hits"]) > 1:
        click.echo(
            "ERROR: Multiple accounts found for '{account}' in index '{index}'",
            err=True,
        )
        sys.exit(1)

    # Update account obj
    doc_id = existing_account_results["hits"]["hits"][0]["_id"]
    account_info = existing_account_results["hits"]["hits"][0]["_source"]
    account_info[f"{charge_type}_charges"] += charges

    # Upload account
    es_client.index(index=index, id=doc_id, body=account_info)
    click.echo(f"Account {account} updated.")


def update_total_charges(
    es_client,
    start_date,
    end_date,
    charge_index="cas-daily-charge-records-*",
    account_index="cas-credit-accounts",
):
    # Loop over charges from time period
    charge_data = get_charge_data(
        es_client,
        start_date,
        end_date,
        charge_index=charge_index,
        account_index=account_index,
    )
    charge_data.sort(key=itemgetter("date", "account_id"))
    for charge in charge_data:
        # Get account data
        account_data = query_account(
            es_client, account=charge["account_id"], index=account_index
        )
        if len(account_data["hits"]["hits"]) == 0:
            click.echo(
                "ERROR: No existing account '{account}' in index '{index}'", err=True
            )
            sys.exit(1)
        if len(account_data["hits"]["hits"]) > 1:
            click.echo(
                "ERROR: Multiple accounts found for '{account}' in index '{index}'",
                err=True,
            )
            sys.exit(1)
        doc = account_data["hits"]["hits"][0]

        doc_id = doc["_id"]
        account_info = doc["_source"]

        # Check dates
        charge_type = charge["charge_type"]
        if charge["date"] <= account_info[f"{charge_type}_last_charge_date"]:
            raise ValueError(
                f"An added {charge_type} charge would come before or on last {charge_type} charge date on account '{account}'"
            )

        # Modify account data
        account_info[f"{charge_type}_charges"] += charge["total_charges"]
        account_info[f"{charge_type}_last_charge_date"] = charge["date"]

        # Upload modified account
        es_client.index(index=account_index, id=doc_id, body=account_info)
