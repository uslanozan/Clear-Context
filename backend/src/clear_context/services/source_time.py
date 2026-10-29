"""Normalize explicit ISO/RFC publication dates without guessing missing dates."""

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from clear_context.schemas.source_time import PublicationContext


def publication_context(values: list[str]) -> PublicationContext:
    parsed, unparsed = set(), set()
    for raw in values:
        value = raw.strip()
        normalized = None
        try:
            normalized = date.fromisoformat(value).isoformat()
        except ValueError:
            try:
                normalized = datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                # RFC dates must carry an explicit year; never supply the current year.
                year = re.search(r"\b\d{1,2}\s+[A-Za-z]{3}\s+(\d{4})\b", value)
                if year:
                    try:
                        parsed_date = parsedate_to_datetime(value)
                        if parsed_date.year == int(year.group(1)):
                            normalized = parsed_date.date().isoformat()
                    except (ValueError, TypeError, OverflowError):
                        pass
        if normalized:
            parsed.add(normalized)
        else:
            unparsed.add(raw)
    status = "missing"
    if len(parsed) > 1:
        status = "conflicting"
    elif unparsed:
        status = "unparseable"
    elif parsed:
        status = "unambiguous"
    return PublicationContext(
        status=status, normalized_dates=sorted(parsed), unparsed_values=sorted(unparsed)
    )
