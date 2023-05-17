import click
import sys
import json
from pathlib import Path
from datetime import date, timedelta
from operator import itemgetter
from elasticsearch.helpers import bulk
from cas_admin.connect import connect
from cas_admin.query_utils import query_account, get_charge_data
import cas_admin.cost_functions as cost_functions


START = date(2022, 2, 20)
YESTERDAY = date.today() - timedelta(days=1)


def get_job_type(job):
    try:
        if job.get("RequestGpus") > 0:
            return "gpu"
    except Exception:
        pass
    return "cpu"


def compute_missing_daily_charges(
    es_client,
    date,
    account_index,
    usage_index,
    old_charge_index,
    new_charge_index,
    account_name_attr="ProjectName",
    dry_run=False,
):
    """Computes missing charges given a time range and converts v1 charge records to v2"""

    account_data = get_account_data(es_client, index=account_index)

    if len(account_data) == 0:
        click.echo(f"ERROR: No accounts found in index '{account_index}'", err=True)
        sys.exit(1)

    for account_info in account_data:
        account = account_info["account_id"]
        v1_account_type = account_info["v1_charge_function"][0:3]
        cost_funcname = {
            "cpu": account_info["cpu_charge_function"],
            "gpu": account_info["gpu_charge_function"],
        }
        account_charges = {
            "cpu": {},
            "gpu": {},
        }

        # Get existing charge data
        for charge_data in get_charge_data(
            es_client,
            start_date=date,
            end_date=date + timedelta(days=1),
            account=account,
            charge_index=old_charge_index,
            account_index=account_index,
        ):
            job_type = v1_account_type
            user = charge_data["user_id"]
            resource_name = charge_data["resource_name"]
            if user not in account_charges[job_type]:
                account_charges[job_type][user] = {}
            account_charges[job_type][user][resource_name] = charge_data[
                "total_charges"
            ]

        # Get missing charge data
        match_terms = {account_name_attr: account}
        for usage_row in get_usage_data(
            es_client,
            date,
            date + timedelta(days=1),
            match_terms=match_terms,
            index=usage_index,
        ):
            job_type = get_job_type(usage_row)
            if job_type == v1_account_type:
                # We already should have this from existing charge data
                continue

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


def apply_missing_daily_charges(
    es_client,
    date,
    account_index,
    charge_index,
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

        # Skip applying existing charges
        v1_account_type = account_infos[account]["v1_charge_function"][0:3]
        if charge_type == v1_account_type:
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


def snapshot_accounts(es_client, index, snapshot_dir, this_date, dry_run=False):
    """Create a backup of account data from previous day.
    Do not allow backups to be overwritten."""
    account_data = query_account(es_client, index=index)
    if len(account_data["hits"]["hits"]) == 0:
        click.echo(f"ERROR: No account data found in index '{index}'")
        sys.exit(1)
    snapshot_file = snapshot_dir / f"cas-credit-accounts_{this_date}.json"
    if snapshot_file.exists():
        click.echo(f"ERROR: Snapshot already exists for date '{this_date}'")
        sys.exit(1)
    if not dry_run:
        with snapshot_file.open("w") as f:
            json.dump(account_data["hits"]["hits"], f, indent=2)
    else:
        click.echo(
            f"Dry run, not writing {len(account_data['hits']['hits'])} account records to {snapshot_file}"
        )


def get_missing_snapshot_dates(snapshot_dir):
    """Count up the days since START in order so that we
    can make sure a snapshot is made (in order) since START"""
    missing_snapshots = []
    n_days = (YESTERDAY - START).days
    for n_day in range(n_days + 1):
        this_date = START + timedelta(days=n_day)
        snapshot_file = snapshot_dir / f"cas-credit-accounts_{this_date}.json"
        if not snapshot_file.exists():
            if (
                len(missing_snapshots) > 0
                and (this_date - missing_snapshots[-1]).days > 1
            ):
                click.echo(
                    """CRITICAL: Snapshot(s) exist between {missing_snapshots[-1]} and {this_date}, 
cannot continue until {missing_snapshot[-1]} exists."""
                )
                sys.exit(1)
            missing_snapshots.append(this_date)
    return missing_snapshots


@click.command()
@click.option("--dry_run", default=False, is_flag=True)
@click.option(
    "--snapshot_dir",
    default=Path("./recomputed-cas-credit-accounts-snapshots"),
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--account_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts"
)
@click.option("--usage_index", envvar="CAS_USAGE_INDEX", default="path-schedd-*")
@click.option(
    "--old_charge_index", default="backup-{date.today()}-cas-daily-charge-records-*"
)
@click.option(
    "--new_charge_index", envvar="CAS_CHARGE_INDEX", default="cas-daily-charge-records"
)
@click.option(
    "--account_name_attr",
    envvar="CAS_ACCOUNT_NAME_ATTR",
    default="ProjectName",
)
@click.option("--es_host", envvar="ES_HOST", default="localhost")
@click.option("--es_user", envvar="ES_USER")
@click.option("--es_pass", envvar="ES_PASS")
@click.option(
    "--es_use_https/--es_no_use_https",
    envvar="ES_USE_HTTPS",
    type=click.BOOL,
    default=False,
)
@click.option("--es_ca_certs", envvar="ES_CA_CERTS", type=click.Path(exists=True))
def main(
    dry_run,
    snapshot_dir,
    account_index,
    usage_index,
    old_charge_index,
    new_charge_index,
    account_name_attr,
    es_host,
    es_user,
    es_pass,
    es_use_https,
    es_ca_certs,
):
    click.echo(
        f"""
dry_run = {dry_run}
snapshot_dir = {snapshot_dir}
account_index = {account_index}
usage_index = {usage_index}
old_charge_index = {old_charge_index}
new_charge_index = {new_charge_index}
account_name_attr = {account_name_attr}
"""
    )
    click.confirm("Do you want to continue?", abort=True)

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    es_client = connect(es_host, es_user, es_pass, es_use_https, es_ca_certs)

    for missing_snapshot_date in get_missing_snapshot_dates(snapshot_dir):
        compute_missing_daily_charges(
            es_client,
            missing_snapshot_date,
            account_index,
            usage_index,
            old_charge_index,
            new_charge_index,
            account_name_attr,
            dry_run,
        )
        apply_missing_daily_charges(
            es_client,
            missing_snapshot_date,
            account_index,
            new_charge_index,
            dry_run,
        )
        snapshot_accounts(
            es_client, account_index, snapshot_dir, missing_snapshot_date, dry_run
        )


if __name__ == "__main__":
    main()
