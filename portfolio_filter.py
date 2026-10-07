import json
import os

from openai import OpenAI

from extractor import CLAUSE_TYPES

_FILTER_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "contract_name": {"type": "string"},
                    "matched": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["contract_name", "matched", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["matches"],
    "additionalProperties": False,
}


def _compact_run(run):
    result = run.get("result", {})
    clauses = {}
    for ct in CLAUSE_TYPES:
        c = result.get("clauses", {}).get(ct, {})
        if c.get("found"):
            clauses[ct] = {
                "summary": c.get("summary_plain") or c.get("summary_legal"),
                "quote": c.get("quote"),
                "flagged": c.get("flagged"),
            }
    return {"contract_name": run.get("contract_name"), "clauses": clauses}


def filter_portfolio(query, runs, model="gpt-4o-mini"):
    """Natural-language filter across saved contract runs, e.g.
    'show me contracts with a liability cap under $10,000'."""
    if not runs:
        return []

    compact = [_compact_run(r) for r in runs]
    prompt = f"""You are filtering a portfolio of contracts based on a user's natural-language query.

QUERY: {query}

For each contract below, decide if it matches the query based on its extracted clauses. Give a one-sentence reason
grounded in the actual clause text/summary shown — do not invent facts not present below. If a contract's relevant
clause wasn't found/extracted, treat it as not matching and say so.

CONTRACTS:
{json.dumps(compact, indent=2)}
"""

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "portfolio_filter", "schema": _FILTER_SCHEMA, "strict": True},
        },
        messages=[{"role": "user", "content": prompt}],
    )
    result = json.loads(response.choices[0].message.content)
    return result["matches"]
