import click
from datetime import date
from pathlib import Path
from cas_admin.connect import connect
from cas_admin.email_utils import send_email, generate_monthly_agency_report


def get_last_month(this_month=date.today().month):
    month = [None, 12] + list(range(1, 12))
    year = [None, date.today().year - 1] + 11 * [date.today().year]
    return date(year[this_month], month[this_month], 1)


@click.command()
@click.option(
    "--xlsx_directory",
    envvar="CAS_MONTHLY_AGENCY_REPORT_DIR",
    default=Path("./monthly_agency_reports"),
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--from", "from_addr", required=True)
@click.option("--to", "to_addrs", multiple=True, default=[])
@click.option("--replyto", "replyto_addr", type=str, default=None)
@click.option("--cc", "cc_addrs", multiple=True, default=[])
@click.option("--bcc", "bcc_addrs", multiple=True, default=[])
@click.option("--admin", "admin_addrs", multiple=True, default=[])
@click.option("--smtp_server", type=str, default=None)
@click.option("--smtp_username", type=str, default=None)
@click.option(
    "--smtp_password_file",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
)
@click.option(
    "--account_index", envvar="CAS_ACCOUNT_INDEX", default="cas-credit-accounts"
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
    account_index,
    from_addr,
    to_addrs,
    replyto_addr,
    cc_addrs,
    bcc_addrs,
    admin_addrs,
    smtp_server,
    smtp_username,
    smtp_password_file,
):
    es_client = connect(es_host, es_user, es_pass, es_use_https, es_ca_certs)

    errors = []
    last_month = get_last_month()

    # Send monthly account report
    subject = f"Monthly PATh Credit Accounts Report for {last_month.strftime('%b %Y')}"
    try:
        attachments = generate_monthly_accounts_report(
            es_client, last_month, xlsx_directory, account_index
        )
        html = attachments.pop("html")
        send_email(
            from_addr,
            list(to_addrs),
            subject,
            replyto_addr,
            list(cc_addrs),
            list(bcc_addrs),
            list(attachments.values()),
            html,
            smtp_server,
            smtp_username,
            smtp_password_file,
        )
    except Exception as e:
        error_str = f"Error while sending '{subject}':\n\t{str(e)}"
        click.echo(error_str, err=True)
        errors.append(error_str)

    # Send email with errors to admins
    if len(errors) > 0:
        error_html = f"<html><body>{'<br><br>'.join(errors)}</body></html>"
        send_email(
            from_addr, list(admin_addrs), f"Error sending {subject}", html=error_html
        )


if __name__ == "__main__":
    main()
