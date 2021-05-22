from datetime import datetime, timedelta

import humanize
import numpy as np
from flask_login import current_user

from models import Booking, GymBooking
from time_utils import start_of_day, start_of_week, timeslot_index
from utils import get_chosen_gym, is_admin, get_zone, is_instructor

TS_M = 15
TS_S = TS_M * 60


def create_from_to(f, t, days):
    new_booking = np.zeros(24 * 4 * days)
    for x in range(f, t):
        new_booking[x] += 1
    return new_booking


def create_daily_from_to(f, t):
    new_booking = np.zeros(24 * 4)
    for x in range(f, t):
        new_booking[x] += 1
    return new_booking


def validate_booking(start, end, number, zone_id):

    gym = get_chosen_gym()
    if zone_id not in [x.id for x in gym.zones]:
        raise AssertionError("The zone has been removed. Please refresh page and try again.")

    zone = get_zone(zone_id)

    # First we check general stuff
    if start.date() != end.date():
        raise AssertionError("Start end stop must be on same day")

    if end <= start:
        raise AssertionError("Start must come before end")

    # Then we check capacity
    all_bookings = create_daily_booking_map(start, zone_id)

    start_end_array = create_daily_from_to(timeslot_index(start), timeslot_index(end)) * number
    if zone.max_people and np.any((all_bookings + start_end_array) > zone.max_people):
        raise AssertionError(f"Booking exceeds zone capacity")
    elif gym.max_people and np.any((all_bookings + start_end_array) > gym.max_people):
        raise AssertionError(f"Booking exceeds gym capacity")

    if is_admin() or is_instructor():
        return

    if number > (gym.max_number_per_booking if gym.max_number_per_booking else gym.max_people):
        raise AssertionError(f"Max persons per booking is {get_chosen_gym().max_number_per_booking}")

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

    if gym.max_booking_length and ((end - start).total_seconds() / TS_S) > gym.max_booking_length:
        maxlen = humanize.precisedelta(timedelta(seconds=gym.max_booking_length * TS_S))
        raise AssertionError(f"Max booking length is {maxlen}")

    book_before = gym.book_before if gym.book_before is not None else 0
    active_bookings = len([x for x in current_user.bookings if x.end - timedelta(minutes=TS_M*book_before) >= datetime.now()])

    if gym.max_booking_per_user is not None and \
            active_bookings >= gym.max_booking_per_user:
        raise AssertionError(f"You can only have {gym.max_booking_per_user} active bookings")

    if gym.max_time_per_user_per_day is not None:
        total_seconds = sum((x.end - x.start).total_seconds() for x in current_user.bookings if x.start.date() == start.date())
        if ((total_seconds + (end - start).total_seconds()) / TS_S) > gym.max_time_per_user_per_day:
            maxlen = humanize.precisedelta(timedelta(seconds=gym.max_time_per_user_per_day * TS_S))
            raise AssertionError(f"You can not book more than {maxlen} per day")


def create_repeating_booking_map(start, days, zone_id):
    all_bookings = np.zeros(24 * 4 * days)

    for b in GymBooking.query\
            .filter(GymBooking.start <= start + timedelta(days=days + 1))\
            .filter_by(zone_id=zone_id).all():

        if b.repeat_end and b.repeat_end < (start + timedelta(days=days + 1)):
            continue

        if b.repeat == "w":

            for dt in range(days):
                _day = start + timedelta(days=dt)
                if _day.weekday() == b.start.weekday():
                    new_start = b.start.replace(year=_day.year, month=_day.month, day=_day.day)
                    new_end = b.end.replace(year=_day.year, month=_day.month, day=_day.day)
                    start_ts = timeslot_index(new_start, start)
                    end_ts = timeslot_index(new_end, start)
                    start_end_array = create_from_to(start_ts, end_ts, days) * b.number

                    all_bookings += start_end_array

    return all_bookings


def create_daily_booking_map(d, zone_id):

    day = start_of_day(d)

    all_bookings = create_repeating_booking_map(day, 1, zone_id) #np.zeros(24 * 4)

    for b in Booking.query.filter(Booking.start >= day).filter(Booking.end <= day + timedelta(days=1)).filter_by(zone_id=zone_id).all():
        start = (b.start - day).total_seconds() / TS_S
        end = (b.end - day).total_seconds() / TS_S

        start_end_array = create_daily_from_to(int(start), int(end)) * b.number

        all_bookings += start_end_array

    return all_bookings


def create_weekly_booking_map(d, zone, days=7):
    week_start_day = start_of_week(d)
    week_end = week_start_day + timedelta(days=days)

    all_bookings = np.zeros(24 * 4 * days)
    my_bookings = np.zeros(24 * 4 * days)

    for b in Booking.query.filter(Booking.start >= week_start_day).filter(
            Booking.end <= week_end).filter_by(zone_id=zone).all():
        start = timeslot_index(b.start, week_start_day)
        end = timeslot_index(b.end, week_start_day)

        start_end_array = create_from_to(start, end, days) * b.number

        all_bookings += start_end_array

        if current_user and b.user.id == current_user.id:
            my_bookings += start_end_array

    all_bookings += create_repeating_booking_map(week_start_day, days, zone)

    return all_bookings, my_bookings
