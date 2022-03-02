# Credit Accounting Service

The PATh Credit Accounting Service
keeps track of computing usage
for users with an allocation
on PATh hardware.
This repository contains collections of scripts and Elasticsearch templates
along with the `cas_admin` commandline tool and Python library.
The CLI tool allows PATh admins to create accounts,
to add credits to accounts,
and to keep tabs on accounts.
The Python library provides functions
for calculating charges
and sending email reports to
account owners and PATh admins.

## cas_admin usage

The `cas_admin` tool provides the
administrative interface for adding, modifying, and viewing credit accounts
Available commands are:

* `cas_admin get accounts` - View credit account(s)
* `cas_admin create account` - Create a credit account
* `cas_admin edit account` - Modify a credit account's owner or email
* `cas_admin add credits` - Add credits to a credit account
* `cas_admin get charges` - View credit charges for a given date

To get help on any of these commands, use --help after the command, for example:
```bash
$ cas_admin create account --help
```

### cas_admin command examples

List accounts
```bash
$ cas_admin get accounts
Name         Type     Owner        Credits Charges PctUsed Remain
GregsCookies cpu_2022 Jason Patton    40.0     0.6    1.5%   39.4
```

Create a new account "AliceGroup" for account owner "Alice Smith"
```bash
$ cas_admin create account AliceGroup --owner "Alice Smith" --email alice.smith@uni.edu --type cpu_2022 --credits 50
account AliceGroup added.
```

List detailed information for account "AliceGroup"
```bash
$ cas_admin get accounts --name AliceGroup
Account Name:	AliceGroup
Account Type:	cpu_2022
Owner:	Alice Smith
Owner Email:	alice.smith@uni.edu
Total Credits:	50.00
Total Charges:	0.00
Pct Credits Used:	0.00%
Credits Remaining:	50.00
```

Add 25 credits to account "AliceGroup"
```bash
$ cas_admin add credits AliceGroup 25
Account AliceGroup updated.
```

Remove 10 credits from account "AliceGroup"
```bash
$ cas_admin add credits AliceGroup -- -10
Account AliceGroup updated.
```

List all charges from Feb 23, 2022
```bash
$ cas_admin get charges --date 2022-02-23
Date       Account      Charge Resource
2022-02-23 GregsCookies    0.6 UNKNOWN
```

### cas_admin full command documentation

Here is a lightly edited list of `--help` output for each `cas_admin` command:

```
Usage: cas_admin COMMAND [ARGS]...

  Administration tool for the PATh Credit Accounting Service

  The PATh Credit Accounting Service keeps track of computing usage for users
  with an allocation on PATh hardware. The cas_admin tool provides the
  administrative interface for adding, modifying, and viewing credit accounts.
  Available commands are:

  cas_admin get accounts - View credit account(s)
  cas_admin create account - Create a credit account
  cas_admin edit account - Modify a credit account's owner or email
  cas_admin add credits - Add credits to a credit account
  cas_admin get charges - View credit charges for a given date

  To get help on any of these commands, use --help after the command, for
  example:

  cas_admin create account --help

---

Usage: cas_admin get accounts [OPTIONS]

  Display credit accounts.

Options:
  --name ACCOUNT_NAME             Get detailed output for credit account
                                  ACCOUNT_NAME.
  --sortby [Name|Type|Owner|Credits|Charges|PctUsed|Remain]
                                  Sort table by given field, defaults to Name.
  --reverse                       Reverse table sorting.

---

Usage: cas_admin create account [OPTIONS] ACCOUNT_NAME

  Create a credit account named ACCOUNT_NAME.

  The account name is case-sensitive, so be sure to double-check your input.
  By default, the account will start with 0 credits, but you can provide a
  different starting amount.

  For proper command parsing, you may want to surround your input for the
  owner in quotes, for example:

  cas_admin create account AliceGroup --owner "Alice Smith" --email alice.smith@wisc.edu --type cpu_2022

Options:
  --owner TEXT                [required]
  --email TEXT                [required]
  --type [cpu_2022|gpu_2022]  [required]
  --credits CREDITS

---

Usage: cas_admin edit account [OPTIONS] ACCOUNT_NAME

  Modify the owner and/or email of credit account named ACCOUNT_NAME.

Options:
  --owner TEXT
  --email TEXT

---

Usage: cas_admin add credits ACCOUNT_NAME CREDITS

  Add CREDITS credits to credit account ACCOUNT_NAME.

  For example, to add 10 credits to AliceGroup:

  cas_admin add credits AliceGroup 10

  If needed, you can subtract credits from an account by specifying "--"
  first:

  cas_admin add credits -- AliceGroup -10

---

Usage: cas_admin get charges [OPTIONS]

  Displays charges accrued by account(s) from a single day.

  Defaults to displaying yesterday's charges from all credit accounts. A
  specified --date value must be in YYYY-MM-DD format.

Options:
  --date [%Y-%m-%d]    Display charges from given date, defaults to yesterday.
  --name ACCOUNT_NAME  Display charges only for credit account ACCOUNT_NAME
```

## License
[MIT](https://choosealicense.com/licenses/mit/)