import click
import sys
from collections import OrderedDict
from operator import itemgetter

from cas_admin.query_utils import query_user, get_user_data


def display_user(es_client, user, index="cas-users"):
    """Displays user info"""

    if not "@" in user:
        click.echo(
            "ERROR: User ID must be in format username@access.point.hostname", err=True
        )
        sys.exit(1)

    user_data = get_user_data(es_client, user=user, index=index)

    if len(user_data) == 0:
        click.echo(f"ERROR: No user '{user}' found in index '{index}'", err=True)
        sys.exit(1)
    if len(user_data) > 1:
        click.echo(
            f"ERROR: Multiple hits found for user '{user}' in index '{index}'", err=True
        )
        sys.exit(1)

    row = user_data[0]
    click.echo(f"User ID: {row['user_id']}")
    click.echo(f"Permitted Credit Accounts:\n\t{row['permitted_credit_accounts']}")


def display_all_users(es_client, index="cas-users"):
    """Displays all users info"""

    columns = OrderedDict()
    columns["user_id"] = "User"
    columns["permitted_credit_accounts"] = "Accounts"

    user_data = get_user_data(es_client, index=index)

    if len(user_data) == 0:
        click.echo(f"ERROR: No users found in index '{index}'", err=True)
        sys.exit(1)

    user_data.sort(key=itemgetter("user_id"))

    # Get col sizes
    col_size = {col: len(col_name) for col, col_name in columns.items()}
    for row in user_data:
        for col in columns:
            col_size[col] = max(col_size[col], len(row[col]))

    # Print cols
    items = []
    for col, col_name in columns.items():
        val = col_name.ljust(col_size[col])
        items.append(val)
    click.echo(" ".join(items).rstrip())
    for row in user_data:
        items = []
        for col in columns:
            val = row[col].ljust(col_size[col])
            items.append(val)
        click.echo(" ".join(items).rstrip())


def add_user(es_client, user, permitted_credit_accounts, index="cas-users"):
    """Adds user"""

    # Check input
    if not "@" in user:
        click.echo(
            "ERROR: User ID must be in format username@access.point.hostname", err=True
        )
        sys.exit(1)

    # Check existing
    if len(query_user(es_client, user=user, index=index)["hits"]["hits"]) > 0:
        click.echo(
            "ERROR: Existing user {user} already found in index {index}", err=True
        )
        sys.exit(1)

    # Create user obj
    user_info = {
        "user_id": user,
        "permitted_credit_accounts": permitted_credit_accounts,
    }
    doc_id = user

    # Upload user
    es_client.index(index=index, id=doc_id, body=user_info)
    click.echo(f"User {user} added.")


def edit_permitted_credit_accounts(
    es_client, user, permitted_credit_accounts, index="cas-users"
):
    """Modifies user's permitted credit accounts"""

    # Check input
    if not "@" in user:
        click.echo(
            "ERROR: User ID must be in format username@access.point.hostname", err=True
        )
        sys.exit(1)

    # Check existing
    existing_user_results = query_user(es_client, user=user, index=index)
    if len(existing_user_results["hits"]["hits"]) == 0:
        click.echo("ERROR: No existing user {user} in index {index}", err=True)
        sys.exit(1)
    if len(existing_user_results["hits"]["hits"]) > 1:
        click.echo("ERROR: Multiple users found for {user} in index {index}")
        sys.exit(1)

    # Update user obj
    doc_id = existing_user_results["hits"]["hits"][0]["_id"]
    user_info = existing_user_results["hits"]["hits"][0]["_source"]
    user_info["permitted_credit_accounts"] = permitted_credit_accounts

    # Upload user
    es_client.index(index=index, id=doc_id, body=user_info)
    click.echo(f"User {user} updated.")
