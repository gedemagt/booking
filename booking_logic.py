from datetime import datetime, timedelta

import humanize
import numpy as np
from flask_login import current_user

from models import Booking, Zone
from time_utils import start_of_day, start_of_week, timeslot_index
from utils import get_chosen_gym, is_admin


def create_from_to(f, t):
    new_booking = np.zeros(24 * 4 * 7)
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


def create_daily_booking_map(d, zone_id=None):
    day = start_of_day(d)

    all_bookings = np.zeros(24 * 4)
    zone_bookings = np.zeros(24 * 4)

    for b in Booking.query.filter(Booking.start >= day).filter(Booking.end <= day + timedelta(days=1)).filter_by(zone_id=zone_id).all():
        start = (b.start - day).total_seconds() / 60 / 15
        end = (b.end - day).total_seconds() / 60 / 15

        start_end_array = create_daily_from_to(int(start), int(end)) * b.number

        all_bookings += start_end_array

        if zone_id and b.zone.id == zone_id:
            zone_bookings += start_end_array

    return all_bookings, zone_bookings


def create_weekly_booking_map(d, zone):
    week_start_day = start_of_week(d)
    week_end = week_start_day + timedelta(days=7)

    all_bookings = np.zeros(24 * 4 * 7)
    my_bookings = np.zeros(24 * 4 * 7)

    for b in Booking.query.filter(Booking.start >= week_start_day).filter(
            Booking.end <= week_end).filter_by(zone_id=zone).all():
        start = timeslot_index(b.start, week_start_day)
        end = timeslot_index(b.end, week_start_day)

        start_end_array = create_from_to(start, end) * b.number

        all_bookings += start_end_array

        if current_user and b.user.id == current_user.id:
            my_bookings += start_end_array

    return all_bookings, my_bookings
