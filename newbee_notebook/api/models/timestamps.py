"""Serialize legacy database wall times with an explicit server-local offset."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator


def _timestamp_with_offset(value: datetime) -> datetime:
    # Persistence uses datetime.now() and timezone-naive columns. Interpret
    # those values in the server's timezone; preserve already-aware values.
    if value.tzinfo is None:
        value = value.astimezone()
    return value


ApiTimestamp = Annotated[datetime, AfterValidator(_timestamp_with_offset)]
