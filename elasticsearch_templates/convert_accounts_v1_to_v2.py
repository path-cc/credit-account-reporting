from cas_admin.connect import connect
from datetime import date
from time import time
from pprint import pprint
from pathlib import Path
import os
import json


ACCOUNT_INDEX = os.environ.get("CAS_ACCOUNT_INDEX", "cas-credit-accounts")
ACCOUNT_JSON_FILE = Path("indices") / "cas-credit-accounts.json"

DRY_RUN = True


def get_v1_docs(es, index):
    docs = {}
    for result in es.search(index=index, size=1024)["hits"]["hits"]:
        doc_id = result["_id"]
        docs[doc_id] = result["_source"]
    return docs


def pop_credits_and_dates(v1_type, v1, v2):
    typeA = v1_type[0:3]
    v1[f"{typeA}_charge_function"] = v1_type
    for v1_field in [
        "total_charges",
        "total_credits",
        "last_charge_date",
        "last_credit_date",
    ]:
        if v1_field in v1:
            v2_field = v1_field.replace("total_", "")
            v2[f"{typeA}_{v2_field}"] = v1.pop(v1_field)
    typeB = "cpu" if typeA == "gpu" else "gpu"
    v2[f"{typeB}_charge_function"] = f"{typeB}_{v1_type[-4:]}"
    v2[f"{typeB}_credits"] = 0
    v2[f"{typeB}_last_credit_date"] = str(date.today())


def convert_v1_docs_to_v2_docs(v1_docs):
    v2_docs = {}
    for doc_id, v1_doc in v1_docs.items():
        if "type" not in v1_doc:
            continue
        v1_type = v1_doc.pop("type")
        v2_doc = {
            "cas_version": "v2",
            "v1_charge_function": v1_type,
        }
        pop_credits_and_dates(v1_type, v1_doc, v2_doc)
        v2_doc.update(v1_doc)
        v2_docs[doc_id] = v2_doc
    return v2_docs


def update_account_docs(es, index, docs, dry_run=False):
    print()
    for doc_id, doc in docs.items():
        print(f"Updating {doc_id}")
        if dry_run:
            pprint(doc)
        if not dry_run:
            es.index(index=index, id=doc_id, document=doc)


def main():
    es = connect()

    # 1. Get docs
    v1_docs = get_v1_docs(es, ACCOUNT_INDEX)
    if DRY_RUN:
        print("Old account docs:")
        pprint(v1_docs)

    # 2. Convert docs
    v2_docs = convert_v1_docs_to_v2_docs(v1_docs)
    if DRY_RUN:
        print("New account docs:")
        pprint(v2_docs)

    # 3. Update docs
    update_account_docs(es, ACCOUNT_INDEX, v2_docs, DRY_RUN)


if __name__ == "__main__":
    main()
