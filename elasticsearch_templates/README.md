# Elasticsearch templates, upgrades, and related scripts

## Setting up a dev environment

1. `clone_prod_to_dev.py`: Copies `cas-credit-accounts` to `dev-cas-credit-accounts` and `cas-daily-charge-records-*` to `dev-cas-daily-charge-records-*` and fixes templates and ILM policies.
2. `reset_dev.py`: "Truncates" the dev environment -- removes all (dev) charge records and sets charges back to 0 in all (dev) account records.

## Upgrading Elasticsearch indices from CAS v1 to v2

Consider testing steps 2-4 in a dev environment first by sourcing `../scripts/activate_cas_dev_environment`.

1. Backup existing indices:
  - `backup_prod_accounts.py`: Copies `cas-credit-accounts` to `backup-{yyyy-mm-dd}-cas-credit-accounts`.
  - `backup_prod_charges.py`: Copies `cas-daily-charge-records-*` to `backup-{yyyy-mm-dd}-cas-daily-charges-records-*`.
2. Clear out existing `cas-daily-charge-records-*` indexes (necessary for step 4 below).
3. Update Elasticsearch objects:
  - `push_templates_to_elasticsearch.py`: Updates the account and charge indices, templates, aliases, and ILM policies to the latest versions.
  - `convert_accounts_v1_to_v2.py`: Converts existing "v1" account docs to "v2", where v1 accounts are specifically CPU or GPU and v2 accounts contain credits for both job types.
4. Recompute missing charges:
  - `recompute_daily_charges`: Backfills v2 accounts' (a) CPU usages for accounts that used to be GPU-only and (b) GPU usages for acounts that used to be CPU-only. Requires a backup set of charges to read from. Will not touch original charges.
