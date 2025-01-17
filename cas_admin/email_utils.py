import click
import xlsxwriter
import json
import time
import smtplib
import dns.resolver
from operator import itemgetter
from collections import OrderedDict
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from cas_admin.account import get_account_data, get_charge_data


def _smtp_mail(
    msg, recipient, smtp_server=None, smtp_username=None, smtp_password=None
):
    sent = False
    result = None
    tries = 0
    sleeptime = 0
    while tries < 3 and sleeptime < 600:
        try:
            if smtp_username is None:
                smtp = smtplib.SMTP(smtp_server)
            else:
                smtp = smtplib.SMTP_SSL(smtp_server)
                smtp.login(smtp_username, smtp_password)
        except Exception:
            click.echo(f"Could not connect to SMTP server: {smtp_server}", err=True)
            continue

        try:
            result = smtp.sendmail(msg["From"], recipient, msg.as_string())
            if len(result) > 0:
                click.echo(
                    f"Could not send email to {recipient} using server {smtp_server}:\n{result}",
                    err=True,
                )
            else:
                sent = True
        except Exception:
            click.echo(
                f"Could not send to {recipient} using server {smtp_server}", err=True
            )
        finally:
            try:
                smtp.quit()
            except smtplib.SMTPServerDisconnected:
                pass
        if sent:
            break

        sleeptime = int(min(30 * 1.5**tries, 600))
        time.sleep(sleeptime)
        tries += 1

    else:
        logger.error(f"Failed to send email after {tries} loops")

    return sent


def send_email(
    from_addr,
    to_addrs=[],
    subject="",
    replyto_addr=None,
    cc_addrs=[],
    bcc_addrs=[],
    attachments=[],
    html="",
    smtp_server=None,
    smtp_username=None,
    smtp_password_file=None,
):
    if len(to_addrs) == 0:
        click.echo("No recipients in the To: field, not sending email", err=True)
        return

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    if len(cc_addrs) > 0:
        msg["Cc"] = ", ".join(cc_addrs)
    if len(bcc_addrs) > 0:
        msg["Bcc"] = ", ".join(bcc_addrs)
    if replyto_addr is not None:
        msg["Reply-To"] = replyto_addr
    msg["Subject"] = subject

    msg.attach(MIMEText(html, "html"))

    for attachment in attachments:
        path = Path(attachment)
        part = MIMEBase("application", "octet-stream")
        with path.open("rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        msg.attach(part)

    if smtp_server is not None:  # use SMTP
        recipient = list(set(to_addrs + cc_addrs + bcc_addrs))
        smtp_password = None
        if smtp_password_file is not None:
            smtp_password = smtp_password_file.open("r").read().strip()
        _smtp_mail(msg, recipient, smtp_server, smtp_username, smtp_password)
    else:  # lookup MX record and send emails directly
        for recipient in to_addrs + cc_addrs + bcc_addrs:
            domain = recipient.split("@")[1]
            sent = False
            result = None
            for mx in dns.resolver.query(domain, "MX"):
                mailserver = str(mx).split()[1][:-1]
                try:
                    smtp = smtplib.SMTP(mailserver)
                    result = smtp.sendmail(from_addr, recipient, msg.as_string())
                    smtp.quit()
                except Exception:
                    click.echo(
                        f"WARNING: Could not send to {recipient} using {mailserver}",
                        err=True,
                    )
                    if result is not None:
                        click.echo(
                            f"WARNING: Got result: {result} from {mailserver}", err=True
                        )
                else:
                    sent = True
                if sent:
                    break
            else:
                click.echo(
                    f"ERROR: Could not send to {recipient} using any mailserver",
                    err=True,
                )


def generate_weekly_accounts_report(
    es_client,
    starting_week_date,
    xlsx_directory=Path("./weekly_accounts_reports"),
    index="cas-credit-accounts",
):
    """Return HTML and XSLX report of per-account credits used and remaining"""

    columns = OrderedDict()
    columns["account_id"] = "Account Name"
    columns["owner"] = "Account Owner"
    columns["percent_cpu_credits_used"] = "% CPU Credits Used"
    columns["cpu_credits"] = "CPU Credits"
    columns["cpu_charges"] = "CPU Charges"
    columns["remaining_cpu_credits"] = "Remaining CPU Credits"
    columns["percent_gpu_credits_used"] = "% GPU Credits Used"
    columns["gpu_credits"] = "GPU Credits"
    columns["gpu_charges"] = "GPU Charges"
    columns["remaining_gpu_credits"] = "Remaining GPU Credits"

    date_str = str(starting_week_date)

    xlsx_directory.mkdir(parents=True, exist_ok=True)
    xlsx_file = xlsx_directory / f"cas-weekly-account-report_{date_str}.xlsx"

    html = """<html>
<head>
</head>
<body style="background-color: white">
<table style="border-collapse: collapse">
"""
    workbook = xlsxwriter.Workbook(str(xlsx_file))
    worksheet = workbook.add_worksheet()

    xlsx_header_fmt = workbook.add_format({"text_wrap": True, "align": "center"})
    xlsx_date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd"})
    xlsx_numeric_fmt = workbook.add_format({"num_format": "#,##0"})
    xlsx_percent_fmt = workbook.add_format({"num_format": "#,##0.00%"})

    def row_style(i):
        if i % 2 == 1:
            return "background-color: #ddd"
        return "background-color: white"

    def col_html(x):
        try:
            x = float(x)
            return f"""<td style="text-align: right; border: 1px solid black">{x:,.1f}</td>"""
        except ValueError:
            return f"""<td style="text-align: left; border: 1px solid black">{x}</td>"""

    # Write header
    i_row = 0
    html += f"""<tr style="{row_style(0)}">\n"""
    for i_col, (column_id, column_name) in enumerate(columns.items()):
        html += f"""<th style="text-align: center; border: 1px solid black">{column_name}</th>"""
        worksheet.write(i_row, i_col, column_name, xlsx_header_fmt)
    html += "</tr>\n"

    # Get row data
    addl_cols = [
        "percent_cpu_credits_used",
        "remaining_cpu_credits",
        "percent_gpu_credits_used",
        "remaining_gpu_credits",
    ]
    rows = get_account_data(es_client, addl_cols=addl_cols, index=index)

    # Add row data to html and xlsx
    for i_row, row in enumerate(rows, start=1):
        html += f"""<tr style="{row_style(i_row)}">\n"""
        for i_col, col in enumerate(columns):
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
                val = row.get(col, 0)
            else:
                val = row.get(col, "")
            if col in {"percent_cpu_credits_used", "percent_gpu_credits_used"}:
                html += f"""<td style="text-align: right; border: 1px solid black">{val:.1%}</td>"""
                worksheet.write(i_row, i_col, val, xlsx_percent_fmt)
            else:
                html += col_html(val)
                try:
                    worksheet.write(i_row, i_col, float(val), xlsx_numeric_fmt)
                except ValueError:
                    worksheet.write(i_row, i_col, val)
        html += "</tr>\n"
    html += """</table>
</body>
</html>
"""
    workbook.close()

    return {"html": html, "xlsx_file": xlsx_file}


def generate_weekly_account_owner_report(
    es_client,
    account,
    starting_week_date,
    xlsx_directory=Path("./weekly_account_reports_by_account"),
    snapshot_directory=Path("./weekly_accounts_snapshots"),
    account_index="cas-credit-accounts",
    charge_index="cas-daily-charge-records-*",
):
    """Return HTML and XSLX report of per-account credits used and remaining"""

    # Set up global report stuff
    date_str = str(starting_week_date)

    xlsx_directory = xlsx_directory / account
    xlsx_directory.mkdir(parents=True, exist_ok=True)
    xlsx_file = xlsx_directory / f"cas-weekly-account-report_{date_str}.xlsx"

    html = """<html>
<head>
</head>
<body style="background-color: white">
"""
    workbook = xlsxwriter.Workbook(str(xlsx_file))

    xlsx_header_fmt = workbook.add_format({"text_wrap": True, "align": "center"})
    xlsx_date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd"})
    xlsx_numeric_fmt = workbook.add_format({"num_format": "#,##0.0"})
    xlsx_percent_fmt = workbook.add_format({"num_format": "#,##0.0%"})
    xlsx_delta_fmt = workbook.add_format({"num_format": "+#,##0.0;-#,##0.0;0"})
    xlsx_delta_pct_fmt = workbook.add_format(
        {"num_format": "+#,##0.0\%;-#,##0.0\%;0\%"}
    )

    def row_style(i):
        if i % 2 == 1:
            return "background-color: #ddd"
        return "background-color: white"

    def col_style(x):
        try:
            x = float(x)
            return f"""<td style="text-align: right; border: 1px solid black; padding: 4px">{x:,.1f}</td>"""
        except ValueError:
            return f"""<td style="text-align: left; border: 1px solid black; padding: 4px">{x}</td>"""

    # First create the account report
    account_columns = OrderedDict()
    account_columns["account_id"] = "Account Name"
    account_columns["percent_cpu_credits_used"] = "% CPU Credits Used"
    account_columns["cpu_credits"] = "CPU Credits"
    account_columns["cpu_charges"] = "CPU Charges"
    account_columns["remaining_cpu_credits"] = "Remaining CPU Credits"
    account_columns["percent_gpu_credits_used"] = "% GPU Credits Used"
    account_columns["gpu_credits"] = "GPU Credits"
    account_columns["gpu_charges"] = "GPU Charges"
    account_columns["remaining_gpu_credits"] = "Remaining GPU Credits"
    account_columns["owner"] = "Account Owner"
    account_columns["owner_email"] = "Account Owner Email"

    account_worksheet = workbook.add_worksheet("Account summary")
    html += """<h1>Account summary</h1>
<table style="border-collapse: collapse">\n"""

    numeric_cols = {
        "cpu_credits",
        "cpu_charges",
        "remaining_cpu_credits",
        "gpu_credits",
        "gpu_charges",
        "remaining_gpu_credits",
    }

    percent_cols = {
        "percent_cpu_credits_used",
        "percent_gpu_credits_used",
    }

    # Write header
    i_row = 0
    html += f"""<tr>\n"""
    for i_col, (column_id, column_name) in enumerate(account_columns.items()):
        html += f"""<th style="text-align: center; border: 1px solid black; padding: 4px">{column_name}</th>"""
        account_worksheet.write(i_row, i_col, column_name, xlsx_header_fmt)
    html += "</tr>\n"

    # Get row data
    addl_cols = [
        "percent_cpu_credits_used",
        "remaining_cpu_credits",
        "percent_gpu_credits_used",
        "remaining_gpu_credits",
    ]
    rows = get_account_data(
        es_client, account=account, addl_cols=addl_cols, index=account_index
    )
    if len(rows) == 0:
        raise ValueError(f"No account {account} found in index {index}.")
    if len(rows) > 1:
        raise ValueError(
            f"Multiple accounts found for account id {account} in index {index}."
        )
    row = rows[0]

    # Write this week's snapshot file
    snapshot_directory = snapshot_directory / account
    snapshot_directory.mkdir(parents=True, exist_ok=True)
    snapshot_file = snapshot_directory / f"cas-weekly-account-report_{date_str}.json"
    with open(snapshot_file, "w") as f:
        json.dump(row, f, indent=2)

    # Add row data to html and xlsx
    i_row = 1
    html += """<tr>\n"""
    for i_col, col in enumerate(account_columns):
        if col in numeric_cols | percent_cols:
            val = row.get(col, 0)
        else:
            val = row.get(col, "")
        if col in percent_cols:
            html += f"""<td style="text-align: right; border: 1px solid black; padding: 4px">{val:.1%}</td>"""
            account_worksheet.write(i_row, i_col, val, xlsx_percent_fmt)
        else:
            html += col_style(val)
            try:
                account_worksheet.write(i_row, i_col, float(val), xlsx_numeric_fmt)
            except ValueError:
                account_worksheet.write(i_row, i_col, val)
    html += """</tr>\n"""

    # Read from snapshot if available
    last_date_str = str(starting_week_date - timedelta(days=7))
    last_snapshot_file = (
        snapshot_directory / f"cas-weekly-account-report_{last_date_str}.json"
    )
    if last_snapshot_file.exists():
        with last_snapshot_file.open() as f:
            last_row = json.load(f)

        # Adjust for old version
        if last_row.get("cas_version", "v1") == "v1":
            v1_charge_function = last_row["type"]
            orig = v1_charge_function[0:3]
            new = "gpu" if orig_charge_type == "cpu" else "cpu"
            last_row[f"{orig}_credits"] = last_row["total_credits"]
            last_row[f"{orig}_charges"] = last_row["total_charges"]
            last_row[f"remaining_{orig}_credits"] = last_row["remaining_credits"]
            last_row[f"percent_{orig}_credits_used"] = last_row["percent_credits_used"]
            last_row[f"{new}_credits"] = last_row[f"{new}_charges"] = 0.0
            last_row[f"remaining_{new}_credits"] = 0.0
            last_row[f"percent_{new}_credits_used"] = 0.0

        # Add row data to html and xlsx
        i_row = 2
        html += """<tr>\n"""
        merge_to_col = list(account_columns.keys()).index("account_id")
        for i_col, col in enumerate(account_columns):
            if i_col == 0:
                val = "Change since last report"
                html += f"""<td style="text-align: left; border-style: none; padding: 4px" colspan="{merge_to_col+1}">{val}</td>"""
                if i_col == merge_to_col:
                    account_worksheet.write(i_row, i_col, val)
                else:
                    account_worksheet.merge_range(
                        i_row, i_col, i_row, merge_to_col, val
                    )
            elif col in percent_cols:
                val = row.get(col, 0) - last_row.get(col, 0)
                html += f"""<td style="text-align: right; border: 1px solid black; padding: 4px">{val:+,.1f}%</td>"""
                account_worksheet.write(i_row, i_col, val, xlsx_delta_pct_fmt)
            elif col in numeric_cols:
                val = row.get(col, 0) - last_row.get(col, 0)
                html += f"""<td style="text-align: right; border: 1px solid black; padding: 4px">{val:+,.1f}</td>"""
                account_worksheet.write(i_row, i_col, val, xlsx_delta_fmt)
            else:
                if i_col > merge_to_col:
                    html += """<td style="border-style: none"></td>"""
        html += """</tr>\n"""
    html += """</table>\n"""

    def get_bgcolor(charge_type=None, res_type=None):
        if charge_type is None:
            return ""
        if res_type is None:
            res_type = charge_type
        rgbs = {
            "cpu": (255, 238, 204),
            "gpu": (204, 238, 255),
        }
        scales = {
            "cpu": {
                "cpu": 1.00,
                "memory": 0.90,
            },
            "gpu": {
                "cpu": 1.00,
                "gpu": 0.95,
                "memory": 0.90,
            },
        }
        scale = scales.get(charge_type, {}).get(res_type, 1)
        rgb_str = (f"{scale*rgb:.0f}" for rgb in rgbs.get(charge_type, (255, 255, 255)))
        return f"background-color: rgb({', '.join(rgb_str)});"

    def get_col_td(value="", charge_type=None, res_type=None):
        bgcolor = get_bgcolor(charge_type, res_type)
        try:
            value = float(value)
            style = f"text-align: right; border: 1px solid black; padding: 4px; {bgcolor}".strip().rstrip(
                ";"
            )
            return f"""<td style="{style}">{value:,.1f}</td>"""
        except ValueError:
            style = f"text-align: left; border: 1px solid black; padding: 4px; {bgcolor}".strip().rstrip(
                ";"
            )
            return f"""<td style="{style}">{value}</td>"""

    # Now create the charges report
    charge_columns = OrderedDict()
    charge_columns["date"] = "Date"
    charge_columns["user_id"] = "User"
    charge_columns["charge_type"] = "JobType"
    charge_columns["resource_name"] = "Resource"
    charge_columns["total_charges"] = "Charges"
    charges_worksheet = workbook.add_worksheet("Charges summary")
    html += """<h1>Last week's charges</h1>
<table style="border-collapse: collapse">\n"""

    # Write header
    i_row = 0
    html += f"""<tr>\n"""
    for i_col, (column_id, column_name) in enumerate(charge_columns.items()):
        html += f"""<th style="text-align: center; border: 1px solid black; padding: 4px">{column_name}</th>"""
        charges_worksheet.write(i_row, i_col, column_name, xlsx_header_fmt)
    html += """</tr>\n"""

    # Get row data
    rows = get_charge_data(
        es_client,
        start_date=starting_week_date,
        end_date=starting_week_date + timedelta(days=7),
        account=account,
        charge_index=charge_index,
        account_index=account_index,
    )
    rows.sort(key=itemgetter("date", "user_id", "charge_type", "resource_name"))

    # Add row data to html and xlsx
    last_date = "1970-01-01"
    last_user = "nobody@localhost"
    for i_row, row in enumerate(rows, start=1):
        html += """<tr>\n"""
        charge_type = None
        res_type = None
        new_date = True
        new_user = True
        for i_col, col in enumerate(charge_columns):
            if col in numeric_cols | percent_cols:
                val = row.get(col, 0)
            else:
                val = row.get(col, "")
            if col == "date":
                this_date = val
                if this_date == last_date:
                    new_date = False
            elif col == "user_id":
                this_user = val
                if (not new_date) and (this_user == last_user):
                    new_user = False
            elif col == "charge_type":
                charge_type = val
            elif col == "resource_name":
                res_type = val
            if (col == "date" and not new_date) or (col == "user_id" and not new_user):
                html += get_col_td()
            else:
                html += get_col_td(
                    value=val, charge_type=charge_type, res_type=res_type
                )
            try:
                charges_worksheet.write(i_row, i_col, float(val), xlsx_numeric_fmt)
            except ValueError:
                charges_worksheet.write(i_row, i_col, val)
        html += """</tr>\n"""
        last_date = this_date
        last_user = this_user
    html += """</table>\n"""

    html += """</body>
</html>
"""
    workbook.close()

    return {"html": html, "xlsx_file": xlsx_file}


### TODO
# Add monthly NSF report
def generate_monthly_agency_report(
    es_client,
    account,
    starting_month_date,
    xlsx_directory=Path("./monthly_agency_reports"),
    index="cas-credit-accounts",
):
    date_str = str(starting_week_date)

    xlsx_directory = xlsx_directory / account
    xlsx_directory.mkdir(parents=True, exist_ok=True)
    xlsx_file = xlsx_directory / f"path-cas-monthly-agency-report_{date_str}.xlsx"

    html = """<html>
<head>
</head>
<body style="background-color: white">
<table style="border-collapse: collapse">
"""

    workbook = xlsxwriter.Workbook(str(xlsx_file))
    worksheet = workbook.add_worksheet()

    # Create table

    html += """</table>
</body>
</html>
"""
    workbook.close()

    return {"html": html, "xlsx_file": xlsx_file}
