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

## Usage

```bash
# Print the help message
$ cas_admin --help

# List accounts
$ cas_admin get accounts

# Create a new account "AliceGroup" for account owner "Alice Smith"
$ cas_admin create account AliceGroup --owner "Alice Smith" --email alice.smith@wisc.edu --type cpu_2022 --credits 50

# List detailed information for account "AliceGroup"
$ cas_admin get accounts --name AliceGroup

# Add 25 credits to account "AliceGroup"
$ cas_admin add credits AliceGroup 25

# Remove 10 credits from account "AliceGroup"
$ cas_admin add credits AliceGroup -- -10

# Create a user "bob", who submits from "path-submit.chtc.wisc.edu", that can use "AliceGroup" credits
$ cas_admin create user bob@path-submit.chtc.wisc.edu --accounts AliceGroup

# List all charges from yesterday
$ cas_admin get charges

# List all charges from Feb 26, 2022
$ cas_admin get charges --date 2022-02-26
```

Here is a lightly edited list of `--help` output for each `cas_admin` command:

```
Usage: cas_admin COMMAND [ARGS]...

  Administration tool for the PATh Credit Accounting Service

  The PATh Credit Accounting Service keeps track of computing usage for users
  with an allocation on PATh hardware. The cas_admin tool provides the
  administrative interface for adding, modifying, and viewing credit accounts
  and account users. Available commands are:

  Credit account administration commands:
  cas_admin get accounts - View credit account(s)
  cas_admin create account - Create a credit account
  cas_admin edit account - Modify a credit account's owner or email
  cas_admin add credits - Add credits to a credit account
  cas_admin get charges - View credit charges for a given date

  User administration commands:
  cas_admin get users - View user(s)
  cas_admin create user - Create a user
  cas_admin edit user - Change which credit accounts a user can use

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

---

Usage: cas_admin get users [OPTIONS]

  Display users.

Options:
  --name USER_NAME  Get detailed output for user USER_NAME.

---

Usage: cas_admin create user [OPTIONS] USER_NAME

  Create a user account named USER_NAME.

  The user name is case-sensitive and in the format "<username>@<access-point-
  hostname>". Accounts are comma-delimited and should be provided without
  spaces. For example:

  cas_admin create user alice.smith@path-submit.chtc.wisc.edu --accounts AliceGroup,OtherGroup

Options:
  --accounts ACCOUNT_NAMES  Comma-delimited list of credit accounts
                            [required]

---

Usage: cas_admin edit user [OPTIONS] USER_NAME

  Modify the list of credit accounts that USER_NAME can use.

  Accounts are comma-delimited and should be provided without spaces. For
  example:

  cas_admin edit user alice.smith@path-submit.chtc.wisc.edu --accounts AliceGroup,OtherGroup

Options:
  --accounts ACCOUNT_NAMES  Comma-delimited list of accounts the user may
                            charge.  [required]
```

## License
[MIT](https://choosealicense.com/licenses/mit/)