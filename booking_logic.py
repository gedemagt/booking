from datetime import date, datetime, timedelta

import numpy as np
from flask_login import current_user

from models import Booking
from time_utils import start_of_day
from utils import get_chosen_gym


def create_from_to(f, t):
    new_booking = np.zeros(24 * 4 * 7)
    for x in range(f, t):
        new_booking[x] += 1
    return new_booking


def validate_booking(start, end, number):

    gym = get_chosen_gym()

    if start.date() != end.date():
        raise AssertionError("Start end stop must be on same day")

    if gym.max_booking_length and ((end - start).total_seconds() / 60 / 15) > gym.max_booking_length:
        raise AssertionError(f"Max booking length is {gym.max_booking_length} quarters")

    active_bookings = len([x for x in current_user.bookings if x.end >= datetime.now()])

    if gym.max_booking_per_user is not None and \
            active_bookings >= gym.max_booking_per_user:
        raise AssertionError(f"You can only have {gym.max_booking_per_user} active bookings")

    if gym.max_time_per_user_per_day is not None:
        total_seconds = sum((x.end - x.start).total_seconds() for x in current_user.bookings if x.start.date() == start.date())
        if ((total_seconds + (end - start).total_seconds()) / 60 / 15) > gym.max_time_per_user_per_day:
            raise AssertionError(f"You can not book more than {gym.max_time_per_user_per_day} quarters per day")

    overlapping = [x for x in current_user.bookings if
                   (start <= x.start < end) or
                   (start < x.end <= end) or
                   (x.start <= start and x.end >= end)
                   ]
    if len(overlapping) > 0:
        raise AssertionError(
            f"Selection is overlapping with another booking")

    all_bookings = Booking.query\
        .filter_by(user_id=current_user.id)\
        .filter(Booking.start >= start_of_day(start))\
        .filter(Booking.end <= (start_of_day(start) + timedelta(days=1))).all()


    # Todo: Max number

    _max = number
    for b in all_bookings:
        if (start <= b.start < end) or (start < b.end <= end) or (b.start <= start and b.end >= end):
            _max += b.number
    print(_max)


# def get_bookings(d: date):
#     all_bookings = np.zeros(24 * 4)
#     my_bookings = np.zeros(24 * 4)
#     nr_bookings_today = 0
#     for b in Booking.query.filter(Booking.start >= d).filter(Booking.end <= d + timedelta(days=1)).all():
#         start = (b.start - datetime(d.year, d.month, d.day)).seconds / 60 / 15
#         end = (b.end - datetime(d.year, d.month, d.day)).seconds / 60 / 15
#
#         start_end_array = create_from_to(int(start), int(end)) * b.number
#
#         all_bookings += start_end_array
#
#         if current_user and b.user.id == current_user.id:
#             my_bookings += start_end_array
#             nr_bookings_today += 1
#     return np.array(all_bookings), np.array(my_bookings), nr_bookings_today
