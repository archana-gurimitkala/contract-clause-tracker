DEADLINE_SUBJECTS = {
    "renewal_date": "Upcoming renewal — {contract}",
    "termination_notice_deadline": "Action needed: termination notice deadline — {contract}",
}


def draft_renewal_email(contract, deadline_type, date_str, days_until):
    subject_template = DEADLINE_SUBJECTS.get(deadline_type, "Upcoming contract deadline — {contract}")
    subject = subject_template.format(contract=contract)

    if deadline_type == "termination_notice_deadline":
        urgency = (
            f"This is the last day we can send a non-renewal/termination notice under this agreement "
            f"— after {date_str}, it will auto-renew whether or not we intended it to."
        )
    else:
        urgency = f"The current term is set to renew around {date_str}."

    if days_until is not None and days_until < 0:
        timing_line = f"This date has already passed ({abs(days_until)} days ago) — please treat as high priority."
    elif days_until is not None:
        timing_line = f"That's {days_until} day(s) from today."
    else:
        timing_line = ""

    body = f"""Hi,

Flagging an upcoming deadline on {contract}: {deadline_type.replace('_', ' ')} is {date_str}. {timing_line}

{urgency}

Can you confirm whether we want to renew, renegotiate terms, or let this lapse? Happy to pull together a summary of the current terms (and anything flagged as non-standard) if that's useful before we decide.

Thanks,
"""
    return {"subject": subject, "body": body.strip()}
