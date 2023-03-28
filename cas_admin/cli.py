import click
from datetime import datetime, timedelta

from cas_admin.connect import connect
from cas_admin.account import (
    add_account,
    edit_owner,
    add_credits,
    display_account,
    display_all_accounts,
)
from cas_admin.usage import display_charges
import cas_admin.cost_functions as cost_functions

ACCOUNT_TYPES = [x for x in dir(cost_functions) if not x.startswith("_")]

# Using a datetime.datetime object here since click does not generate
# datetime.date objects when using click.DateTime() for option type.
# This will get converted to a datetime.date object later.
YESTERDAY = datetime.now() - timedelta(days=1)


@click.group(no_args_is_help=True, options_metavar=None)
@click.option(
    "--es_host",
    envvar="ES_HOST",
    default="localhost",
    help="Elasticsearch hostname",
    hidden=True,
)
@click.option(
    "--es_user",
    envvar="ES_USER",
    help="Elasticsesarch username (leave blank for none)",
    hidden=True,
)
@click.option(
    "--es_pass",
    envvar="ES_PASS",
    help="Elasticsearch password (leave blank for none)",
    hidden=True,
)
@click.option(
    "--es_use_https/--es_no_use_https",
    envvar="ES_USE_HTTPS",
    type=click.BOOL,
    default=False,
    help="Use HTTPS when connecting to Elasticsearch (defaults to no)",
    hidden=True,
)
@click.option(
    "--es_ca_certs",
    envvar="ES_CA_CERTS",
    type=click.Path(exists=True),
    help="Path to CA certificate bundle to use with Elasticsearch conenctions (defaults to using certs provided by certifi package)",
    hidden=True,
)
@click.pass_context
def cli(ctx, es_host, es_user, es_pass, es_use_https, es_ca_certs):
    """Administration tool for the PATh Credit Accounting Service

    The PATh Credit Accounting Service keeps track of computing usage for users with an allocation on PATh hardware.
    The cas_admin tool provides the administrative interface for adding, modifying, and viewing credit accounts.
    Available commands are:

    \b
    cas_admin get accounts - View credit account(s)
    cas_admin create account - Create a credit account
    cas_admin edit account - Modify a credit account's owner or email
    cas_admin add credits - Add credits to a credit account
    cas_admin get charges - View credit charges for a given date

    To get help on any of these commands, use --help after the command, for example:

    \b
    cas_admin create account --help
    """
    ctx.obj = connect(es_host, es_user, es_pass, es_use_https, es_ca_certs)


@cli.group(no_args_is_help=True, short_help="[account]", options_metavar=None)
@click.pass_context
def create(ctx):
    pass


@create.command("account", no_args_is_help=True, short_help="Create a credit account")
@click.argument("name", metavar="ACCOUNT_NAME")
@click.option("--owner", required=True)
@click.option("--email", required=True)
@click.option("--type", "acct_type", required=True, type=click.Choice(ACCOUNT_TYPES))
@click.option("--credits", "credts", metavar="CREDITS", type=float, default=0.0)
@click.option(
    "--es_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts", hidden=True
)
@click.pass_obj
def create_account(es_client, name, owner, email, acct_type, credts, es_index):
    """Create a credit account named ACCOUNT_NAME.

    The account name is case-sensitive, so be sure to double-check your input.
    By default, the account will start with 0 credits, but you can provide a different starting amount.

    For proper command parsing, you may want to surround your input for the owner in quotes, for example:

    \b
    cas_admin create account AliceGroup --owner "Alice Smith" --email alice.smith@wisc.edu --type cpu_2022"""
    add_account(es_client, name, owner, email, acct_type, credts, es_index)


@cli.group(no_args_is_help=True, short_help="[account]", options_metavar=None)
@click.pass_context
def edit(ctx):
    pass


@edit.command(
    "account",
    no_args_is_help=True,
    short_help="Modify a credit account's owner or email",
)
@click.argument("name", metavar="ACCOUNT_NAME")
@click.option("--owner", type=str, default=None)
@click.option("--email", type=str, default=None)
@click.option(
    "--es_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts", hidden=True
)
@click.pass_obj
def edit_account(es_client, name, owner, email, es_index):
    """Modify the owner and/or email of credit account named ACCOUNT_NAME."""
    edit_owner(es_client, name, owner, email, es_index)


@cli.group(no_args_is_help=True, short_help="[credits]", options_metavar=None)
@click.pass_context
def add(ctx):
    pass


@add.command(
    "credits",
    no_args_is_help=True,
    short_help="Add credits to a credit account",
    options_metavar=None,
)
@click.argument("name", metavar="ACCOUNT_NAME")
@click.argument("credts", metavar="CREDITS", type=float)
@click.option(
    "--es_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts", hidden=True
)
@click.pass_obj
def add_account_credits(es_client, name, credts, es_index):
    """Add CREDITS credits to credit account ACCOUNT_NAME.

    For example, to add 10 credits to AliceGroup:

    \b
    cas_admin add credits AliceGroup 10

    If needed, you can subtract credits from an account by specifying "--" first:

    \b
    cas_admin add credits -- AliceGroup -10"""
    add_credits(es_client, name, credts, es_index)


@cli.group(no_args_is_help=True, short_help="[accounts|charges]", options_metavar=None)
@click.pass_context
def get(ctx):
    pass


@get.command("accounts", short_help="View credit account(s)")
@click.option(
    "--name",
    metavar="ACCOUNT_NAME",
    type=str,
    default=None,
    help="Get detailed output for credit account ACCOUNT_NAME.",
)
@click.option(
    "--sortby",
    type=click.Choice(
        ["Name", "Type", "Owner", "Credits", "Charges", "PctUsed", "Remain"],
        case_sensitive=False,
    ),
    default="Name",
    help="Sort table by given field, defaults to Name.",
)
@click.option("--reverse", is_flag=True, default=False, help="Reverse table sorting.")
@click.option(
    "--es_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts", hidden=True
)
@click.pass_obj
def get_accounts(es_client, name, sortby, reverse, es_index):
    """Display credit accounts."""
    sortby = sortby.casefold()
    sort_map = {
        "name": "account_id",
        "type": "type",
        "owner": "owner",
        "credits": "total_credits",
        "charges": "total_charges",
        "pctused": "percent_credits_used",
        "remain": "remaining_credits",
    }
    if name is not None:
        display_account(es_client, name, es_index)
    else:
        display_all_accounts(es_client, sort_map[sortby], reverse, es_index)


@get.command("charges", short_help="View credit charges from one day")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=YESTERDAY,
    help="Display charges from given date, defaults to yesterday.",
)
@click.option(
    "--name",
    metavar="ACCOUNT_NAME",
    type=str,
    default=None,
    help="Display charges only for credit account ACCOUNT_NAME",
)
@click.option(
    "--by-user",
    "by_user",
    is_flag=True,
    help="Display charges totaled by users",
)
@click.option(
    "--by-resource",
    "by_resource",
    is_flag=True,
    help="Display charges totaled by resource",
)
@click.option(
    "--totals",
    is_flag=True,
    help="Display account totals only",
)
@click.option(
    "--es_index",
    envvar="CAS_CHARGE_INDEX_PATTERN",
    default="cas-daily-charge-records-*",
    hidden=True,
)
@click.pass_obj
def get_charges(es_client, date, name, by_user, by_resource, totals, es_index):
    """Displays charges accrued by account(s) from a single day.

    Defaults to displaying yesterday's charges from all credit accounts.
    A specified --date value must be in YYYY-MM-DD format."""
    start_date = date.date()
    end_date = start_date + timedelta(days=1)
    if totals:
        by_user = True
        by_resource = True
    display_charges(
        es_client, start_date, end_date, name, by_resource, by_user, es_index
    )


if __name__ == "__main__":
    cli()
