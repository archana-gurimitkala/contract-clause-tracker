import json
import os
import re

from openai import OpenAI

CLAUSE_TYPES = [
    "termination",
    "auto_renewal",
    "confidentiality",
    "indemnification",
    "limitation_of_liability",
    "governing_law",
    "payment_terms",
]

DATE_FIELDS = ["effective_date", "renewal_date", "termination_notice_deadline"]

_CLAUSE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "quote": {
            "type": ["string", "null"],
            "description": "Exact verbatim passage from the source text. Null if not found.",
        },
        "summary_legal": {
            "type": ["string", "null"],
            "description": "One or two sentence summary for a lawyer: precise terminology, reference the specific obligation/right. Null if not found.",
        },
        "summary_plain": {
            "type": ["string", "null"],
            "description": "One or two sentence summary for a non-lawyer client: everyday language, no legal jargon, explain what it means for them practically. Null if not found.",
        },
        "flagged": {"type": "boolean"},
        "flag_reason_legal": {
            "type": ["string", "null"],
            "description": "Precise explanation of why this deviates from the playbook's acceptable range, referencing the specific red-flag pattern. Null if not flagged.",
        },
        "flag_reason_plain": {
            "type": ["string", "null"],
            "description": "Plain-English explanation of why this is risky and what could go wrong, written for someone with no legal background. Null if not flagged.",
        },
        "suggested_redline": {
            "type": ["string", "null"],
            "description": "Only when flagged=true: a concise (1-3 sentence) suggested replacement clause adapted from the playbook's acceptable-language example, using this contract's actual party names/defined terms where natural. This is drafted new language, not a quote from the source. Null if not flagged.",
        },
    },
    "required": [
        "found", "quote", "summary_legal", "summary_plain",
        "flagged", "flag_reason_legal", "flag_reason_plain", "suggested_redline",
    ],
    "additionalProperties": False,
}

_DATE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "date": {
            "type": ["string", "null"],
            "description": "ISO 8601 date (YYYY-MM-DD) if a specific calendar date is stated or unambiguously calculable. Null otherwise.",
        },
        "quote": {
            "type": ["string", "null"],
            "description": "Exact verbatim passage this date was derived from. Null if not found.",
        },
    },
    "required": ["found", "date", "quote"],
    "additionalProperties": False,
}

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "contract_type_guess": {
            "type": "string",
            "description": "Best guess at the contract type, e.g. 'NDA', 'MSA', 'Other'.",
        },
        "clauses": {
            "type": "object",
            "properties": {ct: _CLAUSE_RESULT_SCHEMA for ct in CLAUSE_TYPES},
            "required": CLAUSE_TYPES,
            "additionalProperties": False,
        },
        "dates": {
            "type": "object",
            "properties": {df: _DATE_RESULT_SCHEMA for df in DATE_FIELDS},
            "required": DATE_FIELDS,
            "additionalProperties": False,
        },
    },
    "required": ["contract_type_guess", "clauses", "dates"],
    "additionalProperties": False,
}


def _load_playbook(path="contract_playbook.json"):
    with open(path) as f:
        return json.load(f)


def _normalize(text):
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def _build_prompt(contract_text, playbook):
    sections = []
    for ct in CLAUSE_TYPES:
        entry = playbook[ct]
        red_flags = "\n".join(f"  - {rf['pattern']}: {rf['flag_reason']}" for rf in entry["red_flags"])
        sections.append(
            f"### {entry['clause_type']}\n"
            f"What it covers: {entry['what_it_covers']}\n"
            f"Acceptable range: {entry['acceptable_range']}\n"
            f"Red flags:\n{red_flags}\n"
            f"Example acceptable language: {entry['example_acceptable_language']}\n"
            f"Example risky language: {entry['example_risky_language']}"
        )
    playbook_text = "\n\n".join(sections)

    return f"""You are a contract review assistant. Analyze the contract below.

For each of these seven clause types, find the exact passage in the contract that covers it:
termination, auto_renewal, confidentiality, indemnification, limitation_of_liability, governing_law, payment_terms.

STRICT GROUNDING RULES:
- Quote the EXACT text from the contract, character-for-character. Never paraphrase in the "quote" field.
- If a clause type is not present in the contract, set found=false and quote=null. Do not invent or infer text that isn't there.
- Only set flagged=true if the clause's substance deviates from the playbook's acceptable range below, per its red flags.

For each found clause, write TWO versions of the summary and (if flagged) the flag reason:
- summary_legal / flag_reason_legal: precise, for a lawyer — cite the specific right/obligation and red-flag pattern.
- summary_plain / flag_reason_plain: plain English for a client with zero legal background — no jargon, explain practically what it means and what could go wrong.
Keep summary_legal/summary_plain strictly limited to describing the quoted text itself — do not pull in facts from other clauses or sections.

If flagged=true, also draft suggested_redline: a short (1-3 sentence) replacement clause adapted from the playbook's acceptable-language example for that clause type, using this contract's actual party names/defined terms where it reads naturally. This is new drafted language, not a quote — it does not need to match the source text.

Also extract these key dates, if stated or unambiguously calculable from the contract: effective_date, renewal_date, termination_notice_deadline.
Same grounding rule applies: quote the exact source text the date was derived from, and use null if not present.

PLAYBOOK (reference standards to check each clause against):

{playbook_text}

CONTRACT TEXT:

{contract_text}
"""


def _check_grounding(result, source_text):
    normalized_source = _normalize(source_text)
    for ct in CLAUSE_TYPES:
        clause = result["clauses"][ct]
        if clause["found"] and clause["quote"]:
            if _normalize(clause["quote"]) not in normalized_source:
                clause["found"] = False
                clause["flagged"] = False
                clause["flag_reason_legal"] = None
                clause["flag_reason_plain"] = None
                clause["suggested_redline"] = None
                note = "Model-extracted quote could not be verified against the source text — treated as not found."
                clause["summary_legal"] = note
                clause["summary_plain"] = note
                clause["quote"] = None
    for df in DATE_FIELDS:
        date_entry = result["dates"][df]
        if date_entry["found"] and date_entry["quote"]:
            if _normalize(date_entry["quote"]) not in normalized_source:
                date_entry["found"] = False
                date_entry["date"] = None
                date_entry["quote"] = None
    return result


def extract_contract(contract_text, playbook_path="contract_playbook.json", model="gpt-4o"):
    playbook = _load_playbook(playbook_path)
    prompt = _build_prompt(contract_text, playbook)

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "contract_extraction",
                "schema": EXTRACTION_SCHEMA,
                "strict": True,
            },
        },
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content
    result = json.loads(text)
    return _check_grounding(result, contract_text)
