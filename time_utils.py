from datetime import timedelta, datetime


def start_of_week(d=datetime.now()):
    return start_of_day(d - timedelta(days=d.weekday() % 7))


def start_of_day(d):
    return d.replace(hour=0, minute=0, second=0, microsecond=0)