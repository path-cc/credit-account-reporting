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
# See the default help message
$ cas_admin --help

# Create a new account "MyAccount" for account owner "Alice"
$ cas_admin create account MyAccount --owner Alice --email alice@wisc.edu --type cpu_2022 --credits 50

# List accounts
$ cas_admin get accounts

# List detailed information for account "MyAccount"
$ cas_admin get accounts -name MyAccount

# Add 25 credits to account "MyAccount"
$ cas_admin add credits MyAccount 25
```

## License
[MIT](https://choosealicense.com/licenses/mit/)