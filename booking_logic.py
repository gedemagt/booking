import itertools
from datetime import datetime, timedelta
from dateutil import rrule

import humanize
import numpy as np
from flask_login import current_user

from models import Booking, Zone
from time_utils import start_of_day, start_of_week, timeslot_index
from utils import get_chosen_gym, is_admin


def create_daily_from_to(f, t):
    new_booking = np.zeros(24 * 4)
    for x in range(f, t):
        new_booking[x] += 1
    return new_booking


def validate_booking(start, end, number, zone_id):

    gym = get_chosen_gym()
    zone = Zone.query.filter_by(id=zone_id).first()

    # First we check general stuff
    if start.date() != end.date():
        raise AssertionError("Start end stop must be on same day")

    if end <= start:
        raise AssertionError("Start must come before end")

    # Then we check capacity
    all_bookings, zone_bookings = create_daily_booking_map(start, zone_id)

    start_end_array = create_daily_from_to(timeslot_index(start), timeslot_index(end)) * number
    if zone.max_people and np.any((all_bookings + start_end_array) > zone.max_people):
        raise AssertionError(f"Booking exceeds zone capacity")
    elif gym.max_people and np.any((all_bookings + start_end_array) > gym.max_people):
        raise AssertionError(f"Booking exceeds gym capacity")

    if is_admin():
        return

    if gym.max_days_ahead is not None:
        if start.date() > datetime.now().date() + timedelta(days=gym.max_days_ahead):
            raise AssertionError(f"Bookings can only be {gym.max_days_ahead} days into the future")

    overlapping = [
        x for x in current_user.bookings if
        (start <= x.start < end) or
        (start < x.end <= end) or
        (x.start <= start and x.end >= end)
    ]

    if len(overlapping) > 0:
        raise AssertionError(
            f"Selection is overlapping with another booking")

    if gym.max_booking_length and ((end - start).total_seconds() / 60 / 15) > gym.max_booking_length:
        maxlen = humanize.precisedelta(timedelta(seconds=gym.max_booking_length * 15 * 60))
        raise AssertionError(f"Max booking length is {maxlen}")

    active_bookings = len([x for x in current_user.bookings if x.end >= datetime.now()])

    if gym.max_booking_per_user is not None and \
            active_bookings >= gym.max_booking_per_user:
        raise AssertionError(f"You can only have {gym.max_booking_per_user} active bookings")

    if gym.max_time_per_user_per_day is not None:
        total_seconds = sum((x.end - x.start).total_seconds() for x in current_user.bookings if x.start.date() == start.date())
        if ((total_seconds + (end - start).total_seconds()) / 60 / 15) > gym.max_time_per_user_per_day:
            maxlen = humanize.precisedelta(timedelta(seconds=gym.max_time_per_user_per_day * 15 * 60))
            raise AssertionError(f"You can not book more than {maxlen} per day")


MAP = {
    "d": rrule.DAILY,
    "w": rrule.WEEKLY,
    "m": rrule.MONTHLY
}


def create_booking_map(bookings, start, end, timeslot_size=15, zone_id=None):

    number_of_slots = int((end - start).total_seconds() / 60 / timeslot_size)

    all_bookings = np.zeros(number_of_slots)
    my_bookings = np.zeros(number_of_slots)
    zone_bookings = np.zeros(number_of_slots)

    for b in bookings:

        ts = []

        if b.period is None and start <= b.start and b.end <= end:
            ts = [(b.start, b.end)]
        elif b.start <= end:

            diff = b.end - b.start
            start_ts = b.start

            for dt in rrule.rrule(MAP[b.period], dtstart=start_ts, until=end-diff):
                if dt >= start:
                    ts.append((dt, dt+diff))

        for (start_ts, end_ts) in ts:
            start_idx = timeslot_index(start_ts, start, timeslot_size)
            end_idx = timeslot_index(end_ts, start, timeslot_size)

            all_bookings[start_idx:end_idx] += b.number

            if current_user and b.user.id == current_user.id:
                my_bookings[start_idx:end_idx] += b.number
            if zone_id is not None and b.zone == zone_id:
                zone_bookings[start_idx:end_idx] += b.number

    return all_bookings, my_bookings, zone_bookings


def get_bookings_between(start, end, zone):
    normal = Booking.query\
        .filter(Booking.start >= start)\
        .filter(Booking.end <= end)\
        .filter_by(zone_id=zone)\
        .filter(Booking.period is None).all()

    repeating = Booking.query\
        .filter(Booking.start <= end)\
        .filter_by(zone_id=zone)\
        .filter(Booking.period is not None).all()

    return normal, repeating


def create_weekly_booking_map(d, zone):
    week_start_day = start_of_week(d)
    week_end = week_start_day + timedelta(days=7)

    bookings = itertools.chain(*get_bookings_between(week_start_day, week_end, zone))

    all_bookings, my_bookings, _ = create_booking_map(bookings, week_start_day, week_end)

    return all_bookings, my_bookings


def create_daily_booking_map(d, zone_id=None):
    day = start_of_day(d)
    next_day = day + timedelta(days=1)

    bookings = itertools.chain(*get_bookings_between(day, next_day, zone_id))

    all_bookings, _, zone_bookings = create_booking_map(bookings, day, next_day)

    return all_bookings, zone_bookings