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
from cas_admin.user import (
    add_user,
    edit_permitted_credit_accounts,
    display_user,
    display_all_users,
)
from cas_admin.usage import display_charges

# Using a datetime.datetime object here since click does not generate
# datetime.date objects when using click.DateTime() for option type.
# This will get converted to a datetime.date object later.
YESTERDAY = datetime.now() - timedelta(days=1)


@click.group()
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
@click.pass_context
def cli(ctx, es_host, es_user, es_pass, es_use_https, es_ca_certs):
    ctx.obj = connect(es_host, es_user, es_pass, es_use_https, es_ca_certs)


@cli.group()
@click.pass_context
def create(ctx):
    pass


@create.command("account")
@click.argument("name")
@click.option("--owner", required=True)
@click.option("--email", required=True)
@click.option("--type", "acct_type", required=True)
@click.option("--credits", "credts", type=float, default=0.0)
@click.option("--es_index", default="cas-credit-accounts")
@click.pass_obj
def create_account(es_client, name, owner, email, acct_type, credts, es_index):
    add_account(es_client, name, owner, email, acct_type, credts, es_index)


@create.command("user")
@click.argument("name")
@click.option("--accounts")
@click.option("--es_index", default="cas-users")
@click.pass_obj
def create_user(es_client, name, accounts, es_index):
    add_user(es_client, name, accounts, es_index)


@cli.group()
@click.pass_context
def edit(ctx):
    pass


@edit.command("account")
@click.argument("name")
@click.option("--owner", type=str, default=None)
@click.option("--email", type=str, default=None)
@click.option("--es_index", default="cas-credit-accounts")
@click.pass_obj
def edit_account(es_client, name, owner, email, es_index):
    edit_owner(es_client, name, owner, email, es_index)


@edit.command("user")
@click.argument("name")
@click.option("--accounts", required=True)
@click.option("--es_index", default="cas-users")
@click.pass_obj
def edit_user(es_client, name, accounts, es_index):
    edit_permitted_credit_accounts(es_client, name, accounts, es_index)


@cli.group()
@click.pass_context
def add(ctx):
    pass


@add.command("credits")
@click.argument("name")
@click.argument("credts", type=float)
@click.option("--es_index", default="cas-credit-accounts")
@click.pass_obj
def add_account_credits(es_client, name, credts, es_index):
    add_credits(es_client, name, credts, es_index)


@cli.group()
@click.pass_context
def get(ctx):
    pass


@get.command("accounts")
@click.option("--name", type=str, default=None)
@click.option(
    "--sortby",
    type=click.Choice(
        ["Name", "Type", "Owner", "Credits", "Charges", "PctUsed", "Remain"],
        case_sensitive=False,
    ),
    default="Name",
)
@click.option("--reverse", is_flag=True, default=False)
@click.option("--es_index", default="cas-credit-accounts")
@click.pass_obj
def get_accounts(es_client, name, sortby, reverse, es_index):
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


@get.command("users")
@click.option("--name", type=str, default=None)
@click.option("--es_index", default="cas-users")
@click.pass_obj
def get_users(es_client, name, es_index):
    if name is not None:
        display_user(es_client, name, es_index)
    else:
        display_all_users(es_client, es_index)


@get.command("charges")
@click.option("--date", type=click.DateTime(formats=["%Y-%m-%d"]), default=YESTERDAY)
@click.option("--account", type=str, default=None)
@click.option("--es_index", default="cas-daily-charge-records-*")
@click.pass_obj
def get_charges(es_client, date, account, es_index):
    """Displays all charges accrued by account(s) on a given date.
    Defaults to displaying yesterday's charges if --date is not set."""
    start_date = date.date()
    end_date = start_date + timedelta(days=1)
    display_charges(es_client, start_date, end_date, account, es_index)


if __name__ == "__main__":
    cli()
