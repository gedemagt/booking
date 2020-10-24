from datetime import timedelta, datetime


def start_of_week(d=datetime.now()):
    return start_of_day(d - timedelta(days=d.weekday() % 7))


def start_of_day(d):
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def timeslot_index(d, start, slot_length=15):
    return int((d - datetime(start.year, start.month,
                           start.day)).total_seconds() / 60 / slot_length)


def parse(s):
    if s is None:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")