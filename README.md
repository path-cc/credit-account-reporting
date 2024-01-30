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

To get help on any of these commands, add `--help` after the command, for example:
```bash
$ cas_admin create account --help
```

### cas_admin command examples

List accounts
```bash
$ cas_admin get accounts
Name                Owner         Project CpuCredits CpuCharges PctCpuUsed CpuRemain GpuCredits GpuCharges PctGpuUsed GpuRemain
PATh-Staff-Testing  Jason Patton  CHTC       1,100.0       69.4       6.3%   1,030.6        0.0        0.0       0.0%       0.0
```

Create a new account "AliceGroup" for account owner "Alice Smith" with CPU credits
```bash
$ cas_admin create account AliceGroup --owner "Alice Smith" --project ABC123 --email alice.smith@uni.edu --cpu_credits 50
account AliceGroup added.
```

Create a new account "AliceGroup" for account owner "Alice Smith" with CPU and GPU credits
```bash
$ cas_admin create account AliceGroup --owner "Alice Smith" --project ABC123 --email alice.smith@uni.edu --cpu_credits 50 --gpu_credits 50
account AliceGroup added.
```

List detailed information for account "AliceGroup"
```bash
$ cas_admin get accounts --name AliceGroup
Account Name:	AliceGroup
Owner:	Alice Smith
Owner Email:	alice.smith@uni.edu
Owner Project: ABC123
CPU Credits:	50.00
CPU Charges:	0.00
Pct CPU Credits Used:	0.00%
CPU Credits Remaining:	50.00
GPU Credits:	0.00
GPU Charges:	0.00
Pct GPU Credits Used:	0.00%
GPU Credits Remaining:	0.00
```

Add 25 CPU credits to account "AliceGroup"
```bash
$ cas_admin add credits AliceGroup cpu 25
Account AliceGroup updated.
```

Remove 10 CPU credits from account "AliceGroup"
```bash
$ cas_admin add credits AliceGroup cpu -- -10
Account AliceGroup updated.
```

List all charges from Aug 23, 2022
```bash
$ cas_admin get charges --date 2022-08-23
Date       Account            User                            JobType Resource Charge
2022-08-23 PATh-Staff-Testing user.name@submit6.chtc.wisc.edu cpu     cpu         7.5
2022-08-23 PATh-Staff-Testing user.name@submit6.chtc.wisc.edu cpu     memory      0.0
```

## License
[MIT](https://choosealicense.com/licenses/mit/)
