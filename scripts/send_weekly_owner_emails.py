import click
from pathlib import Path
from datetime import date, timedelta
from cas_admin.connect import connect
from cas_admin.email_utils import send_email, generate_weekly_account_owner_report
from cas_admin.query_utils import get_account_emails

IS_MONTHLY = date.today().day <= 7


@click.command()
@click.option(
    "--xlsx_directory",
    envvar="CAS_WEEKLY_BY_ACCOUNT_REPORTS_DIR",
    default=Path("./weekly_account_reports_by_account"),
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--snapshot_directory",
    envvar="CAS_WEEKLY_ACCOUNTS_SNAPSHOTS_DIR",
    default=Path("./weekly_accounts_snapshots"),
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--from", "from_addr", required=True)
@click.option("--to", "to_addrs", multiple=True, default=[])
@click.option("--replyto", "replyto_addr", type=str, default=None)
@click.option("--cc", "cc_addrs", multiple=True, default=[])
@click.option("--bcc", "bcc_addrs", multiple=True, default=[])
@click.option("--admin", "admin_addrs", multiple=True, default=[])
@click.option("--no_email_owners", "no_email_owners", is_flag=True)
@click.option("--account", "account_ids", multiple=True, default=[])
@click.option("--force", "force_send", is_flag=True)
@click.option(
    "--account_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts"
)
@click.option(
    "--charge_index",
    envvar="CAS_CHARGE_INDEX_PATTERN",
    default="cas-daily-charge-records-*",
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
    es_host,
    es_user,
    es_pass,
    es_use_https,
    es_ca_certs,
    xlsx_directory,
    snapshot_directory,
    account_index,
    charge_index,
    from_addr,
    to_addrs,
    replyto_addr,
    cc_addrs,
    bcc_addrs,
    admin_addrs,
    no_email_owners,
    account_ids,
    force_send,
):
    es_client = connect(es_host, es_user, es_pass, es_use_https, es_ca_certs)

    errors = []
    last_week = date.today() - timedelta(days=7)
    active_accounts = get_account_emails(es_client, last_week, account_index)

    # Send weekly account report to owners
    subject_tmpl = f"{date.today()} PATh Credit Account Owner Report"
    for account_id, owner_email in get_account_emails(
        es_client, index=account_index
    ).items():
        if len(account_ids) > 0 and account_id not in account_ids:
            continue
        subject = f"{subject_tmpl} for {account_id}"
        all_to_addrs = list(to_addrs)
        if not no_email_owners:
            all_to_addrs.append(owner_email)
        try:
            attachments = generate_weekly_account_owner_report(
                es_client,
                account_id,
                last_week,
                xlsx_directory,
                snapshot_directory,
                account_index,
                charge_index,
            )
            html = attachments.pop("html")
            if force_send or IS_MONTHLY or account_id in active_accounts:
                send_email(
                    from_addr,
                    list(all_to_addrs),
                    subject,
                    replyto_addr,
                    attachments=list(attachments.values()),
                    html=html,
                )
        except Exception as e:
            error_str = f"Error while sending '{subject}':\n\t{str(e)}"
            click.echo(error_str, err=True)
            errors.append(error_str.replace("\n", "<br>"))

    # Send email with errors to admins
    if len(errors) > 0:
        error_html = f"<html><body>{'<br><br>'.join(errors)}</body></html>"
        send_email(
            from_addr, list(admin_addrs), f"Error sending {subject}", html=error_html
        )


if __name__ == "__main__":
    main()
