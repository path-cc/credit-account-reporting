import click
import sys
import json
from pathlib import Path
from datetime import date, timedelta
from cas_admin.connect import connect
from cas_admin.usage import compute_daily_charges, apply_daily_charges
from cas_admin.query_utils import query_account

START = date(2022, 2, 20)
YESTERDAY = date.today() - timedelta(days=1)


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
@click.option("--override_end_date", default=False, is_flag=True)
@click.option(
    "--snapshot_dir",
    envvar="CAS_SNAPSHOT_DIR",
    default=Path("./cas-credit-accounts-snapshots"),
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--account_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts"
)
@click.option("--usage_index", envvar="CAS_USAGE_INDEX", default="path-schedd-*")
@click.option(
    "--charge_index", envvar="CAS_CHARGE_INDEX", default="cas-daily-charge-records"
)
@click.option(
    "--resource_name_attr",
    envvar="CAS_RESOURCE_NAME_ATTR",
    default="MachineAttrGLIDEIN_ResourceName0",
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
    override_end_date,
    snapshot_dir,
    account_index,
    usage_index,
    charge_index,
    resource_name_attr,
    account_name_attr,
    es_host,
    es_user,
    es_pass,
    es_use_https,
    es_ca_certs,
):

    if override_end_date:
        global YESTERDAY
        YESTERDAY = date.today()

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    es_client = connect(es_host, es_user, es_pass, es_use_https, es_ca_certs)

    previous_account_data = {}
    today_charge_data = {}
    for missing_snapshot_date in get_missing_snapshot_dates(snapshot_dir):
        today_charge_data = compute_daily_charges(
            es_client,
            missing_snapshot_date,
            account_index,
            usage_index,
            charge_index,
            resource_name_attr,
            account_name_attr,
            dry_run,
        )
        previous_account_data.update(
            apply_daily_charges(
                es_client,
                missing_snapshot_date,
                account_index,
                charge_index,
                previous_account_data,
                today_charge_data,
                dry_run,
            )
        )
        snapshot_accounts(
            es_client, account_index, snapshot_dir, missing_snapshot_date, dry_run
        )


if __name__ == "__main__":
    main()
