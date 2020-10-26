from datetime import timedelta, datetime, date


def start_of_week(d=datetime.now()):
    return start_of_day(d - timedelta(days=d.weekday() % 7))


def start_of_day(d):
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def timeslot_index(d, start=None, slot_length=15):
    if start is None:
        start = d
    return int((d - datetime(start.year, start.month,
                           start.day)).total_seconds() / 60 / slot_length)


def as_datetime(k):
    if isinstance(k, datetime):
        return k
    if isinstance(k, date):
        return datetime(k.year, k.month, k.day)
    else:
        try:
            return datetime.strptime(k, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return datetime.strptime(k, "%Y-%m-%d")


def as_date(k):
    if isinstance(k, date):
        return k
    if isinstance(k, datetime):
        return k.date()
    else:
        try:
            return datetime.strptime(k, "%Y-%m-%dT%H:%M:%S").date()
        except ValueError:
            return datetime.strptime(k, "%Y-%m-%d").date()

def parse(s):
    if s is None:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")