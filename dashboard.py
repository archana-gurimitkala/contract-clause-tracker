from datetime import date, datetime


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def days_until(date_str, today=None):
    today = today or date.today()
    d = _parse_date(date_str)
    if d is None:
        return None
    return (d - today).days


def bucket(days):
    if days is None:
        return None
    if days < 0:
        return "overdue"
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def build_dashboard_rows(runs, today=None):
    """runs: list of saved run dicts (see storage.save_run). Returns rows sorted
    by nearest upcoming deadline across renewal_date and termination_notice_deadline."""
    rows = []
    for run in runs:
        dates = run.get("result", {}).get("dates", {})
        for field in ("renewal_date", "termination_notice_deadline"):
            entry = dates.get(field, {})
            date_str = entry.get("date")
            if not date_str:
                continue
            d = days_until(date_str, today=today)
            rows.append(
                {
                    "contract": run.get("contract_name"),
                    "deadline_type": field,
                    "date": date_str,
                    "days_until": d,
                    "bucket": bucket(d),
                }
            )
    rows.sort(key=lambda r: (r["days_until"] is None, r["days_until"]))
    return rows
