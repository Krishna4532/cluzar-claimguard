"""
Dataset Validation Script for ClaimGuard Milestone 1.

Validates synthetic businesses, approved documents, and evaluation cases
against strict structural and referential integrity constraints.
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

BUSINESSES_FILE = DATA_DIR / "businesses.json"
DOCUMENTS_FILE = DATA_DIR / "documents.json"
CASES_FILE = DATA_DIR / "cases.json"

ALLOWED_CLAIM_TYPES = {
    "price",
    "discount_percent",
    "date",
    "product_feature",
    "delivery",
    "return_policy",
    "warranty",
    "other",
}

ALLOWED_VERDICTS = {
    "supported",
    "contradicted",
    "unsupported",
    "needs_human",
}


def validate_dataset() -> bool:
    errors = []

    # 1. Check file existence and JSON parsing
    for file_path in [BUSINESSES_FILE, DOCUMENTS_FILE, CASES_FILE]:
        if not file_path.exists():
            errors.append(f"Missing required file: {file_path}")
            print(f"ERROR: {file_path} not found.")
            return False

    try:
        with open(BUSINESSES_FILE, "r", encoding="utf-8") as f:
            businesses = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse {BUSINESSES_FILE}: {e}")
        businesses = []

    try:
        with open(DOCUMENTS_FILE, "r", encoding="utf-8") as f:
            documents = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse {DOCUMENTS_FILE}: {e}")
        documents = []

    try:
        with open(CASES_FILE, "r", encoding="utf-8") as f:
            cases = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse {CASES_FILE}: {e}")
        cases = []

    if errors:
        for err in errors:
            print(f"PARSING ERROR: {err}")
        return False

    # Lookup dictionaries and tracking sets
    business_ids = set()
    business_map = {}
    product_ids = set()
    product_to_biz = {}
    offer_ids = set()
    offer_to_biz = {}
    document_ids = set()
    document_map = {}
    case_ids = set()
    claim_ids = set()

    total_products = 0
    total_offers = 0

    # 2. Validate Businesses, Products, and Offers
    for b_idx, biz in enumerate(businesses):
        for req in ["business_id", "name", "industry", "currency", "timezone", "products", "offers"]:
            if req not in biz:
                errors.append(f"Business index {b_idx} missing field: '{req}'")

        bid = biz.get("business_id")
        if bid:
            if bid in business_ids:
                errors.append(f"Duplicate business_id: '{bid}'")
            business_ids.add(bid)
            business_map[bid] = biz

        # Validate products
        products = biz.get("products", [])
        if not isinstance(products, list):
            errors.append(f"Business '{bid}': 'products' must be a list")
            products = []

        total_products += len(products)
        biz_prod_ids = set()
        for p_idx, prod in enumerate(products):
            for req in ["product_id", "name", "approved_price", "product_category"]:
                if req not in prod:
                    errors.append(f"Business '{bid}' product index {p_idx} missing field: '{req}'")

            pid = prod.get("product_id")
            if pid:
                if pid in product_ids:
                    errors.append(f"Duplicate product_id: '{pid}' across dataset")
                product_ids.add(pid)
                biz_prod_ids.add(pid)
                product_to_biz[pid] = bid

        # Validate offers
        offers = biz.get("offers", [])
        if not isinstance(offers, list):
            errors.append(f"Business '{bid}': 'offers' must be a list")
            offers = []

        total_offers += len(offers)
        for o_idx, off in enumerate(offers):
            for req in ["offer_id", "applicable_products", "discount_percentage", "validity_dates", "conditions"]:
                if req not in off:
                    errors.append(f"Business '{bid}' offer index {o_idx} missing field: '{req}'")

            oid = off.get("offer_id")
            if oid:
                if oid in offer_ids:
                    errors.append(f"Duplicate offer_id: '{oid}' across dataset")
                offer_ids.add(oid)
                offer_to_biz[oid] = bid

            app_prods = off.get("applicable_products", [])
            for ap in app_prods:
                if ap not in biz_prod_ids:
                    errors.append(f"Offer '{oid}' references product '{ap}' which does not belong to business '{bid}'")

    # 3. Validate Approved Documents
    for d_idx, doc in enumerate(documents):
        for req in ["document_id", "business_id", "document_type", "title", "content"]:
            if req not in doc:
                errors.append(f"Document index {d_idx} missing field: '{req}'")

        did = doc.get("document_id")
        if did:
            if did in document_ids:
                errors.append(f"Duplicate document_id: '{did}'")
            document_ids.add(did)
            document_map[did] = doc

        dbiz = doc.get("business_id")
        if dbiz not in business_ids:
            errors.append(f"Document '{did}' references non-existent business_id: '{dbiz}'")

        content = doc.get("content", "")
        if not isinstance(content, str) or not content.strip():
            errors.append(f"Document '{did}' has empty or invalid content")

    # 4. Validate Cases, Claims, and Evidence
    verdict_counter = Counter()
    total_claims = 0

    for c_idx, case in enumerate(cases):
        for req in ["case_id", "business_id", "draft", "claims"]:
            if req not in case:
                errors.append(f"Case index {c_idx} missing field: '{req}'")

        cid = case.get("case_id")
        if cid:
            if cid in case_ids:
                errors.append(f"Duplicate case_id: '{cid}'")
            case_ids.add(cid)

        cbiz = case.get("business_id")
        if cbiz not in business_ids:
            errors.append(f"Case '{cid}' references non-existent business_id: '{cbiz}'")

        draft = case.get("draft", "")
        if not isinstance(draft, str) or not draft.strip():
            errors.append(f"Case '{cid}' has empty or invalid draft")

        claims = case.get("claims", [])
        if not isinstance(claims, list):
            errors.append(f"Case '{cid}': 'claims' must be a list")
            claims = []

        total_claims += len(claims)

        for cl_idx, claim in enumerate(claims):
            for req in ["claim_id", "text", "type", "gold_verdict", "gold_evidence"]:
                if req not in claim:
                    errors.append(f"Case '{cid}' claim index {cl_idx} missing field: '{req}'")

            claim_id = claim.get("claim_id")
            if claim_id:
                if claim_id in claim_ids:
                    errors.append(f"Duplicate claim_id: '{claim_id}'")
                claim_ids.add(claim_id)

            claim_text = claim.get("text", "")
            # Check claim text is exact substring of draft
            if claim_text not in draft:
                errors.append(
                    f"Claim '{claim_id}' text is not an exact substring of draft in case '{cid}'.\n"
                    f"  Claim text: '{claim_text}'"
                )

            # Check claim type
            ctype = claim.get("type")
            if ctype not in ALLOWED_CLAIM_TYPES:
                errors.append(f"Claim '{claim_id}' has invalid type: '{ctype}'. Allowed: {ALLOWED_CLAIM_TYPES}")

            # Check verdict
            verdict = claim.get("gold_verdict")
            if verdict not in ALLOWED_VERDICTS:
                errors.append(f"Claim '{claim_id}' has invalid gold_verdict: '{verdict}'. Allowed: {ALLOWED_VERDICTS}")
            else:
                verdict_counter[verdict] += 1

            evidence = claim.get("gold_evidence", [])
            if not isinstance(evidence, list):
                errors.append(f"Claim '{claim_id}' 'gold_evidence' must be a list")
                evidence = []

            # Rules for evidence based on verdict
            if verdict in {"supported", "contradicted"}:
                if len(evidence) == 0:
                    errors.append(f"Claim '{claim_id}' with verdict '{verdict}' must have at least one gold_evidence entry")
            elif verdict == "unsupported":
                if len(evidence) > 0:
                    errors.append(f"Claim '{claim_id}' with verdict 'unsupported' must have an empty gold_evidence array")

            # Validate each evidence item
            for ev_idx, ev in enumerate(evidence):
                for req in ["document_id", "source_text"]:
                    if req not in ev:
                        errors.append(f"Claim '{claim_id}' evidence index {ev_idx} missing field: '{req}'")

                edoc_id = ev.get("document_id")
                if edoc_id not in document_ids:
                    errors.append(f"Claim '{claim_id}' evidence references non-existent document_id: '{edoc_id}'")
                    continue

                ref_doc = document_map[edoc_id]
                # Check business consistency
                if ref_doc.get("business_id") != cbiz:
                    errors.append(
                        f"Claim '{claim_id}' in case '{cid}' (business '{cbiz}') references document '{edoc_id}' "
                        f"which belongs to business '{ref_doc.get('business_id')}'"
                    )

                # Check exact substring match in document content
                source_text = ev.get("source_text", "")
                doc_content = ref_doc.get("content", "")
                if source_text not in doc_content:
                    errors.append(
                        f"Claim '{claim_id}' evidence source_text is not an exact substring of document '{edoc_id}'.\n"
                        f"  Source text: '{source_text}'"
                    )

    # Print Summary Report
    print("=" * 60)
    print(" CLAIMGUARD DATASET VALIDATION REPORT")
    print("=" * 60)
    print(f"Total Businesses:       {len(business_ids)}")
    print(f"Total Products:         {total_products}")
    print(f"Total Offers:           {total_offers}")
    print(f"Total Documents:        {len(document_ids)}")
    print(f"Total Evaluation Cases: {len(case_ids)}")
    print(f"Total Labelled Claims:  {total_claims}")
    print("-" * 60)
    print("Verdict Distribution:")
    for v in ["supported", "contradicted", "unsupported", "needs_human"]:
        count = verdict_counter[v]
        pct = (count / total_claims * 100) if total_claims else 0
        print(f"  - {v:<15}: {count:>2} ({pct:>5.1f}%)")
    print("-" * 60)

    if errors:
        print(f"\n[FAILED] {len(errors)} validation error(s) detected:")
        for i, err in enumerate(errors, 1):
            print(f"{i}. {err}")
        return False
    else:
        print("\n[PASSED] All integrity checks succeeded with 0 errors!")
        return True


if __name__ == "__main__":
    success = validate_dataset()
    sys.exit(0 if success else 1)

