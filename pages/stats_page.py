from collections import defaultdict
from datetime import datetime, timedelta

import dash_core_components as dcc
import dash_bootstrap_components as dbc
import numpy as np

from booking_logic import create_weekly_booking_map, create_daily_from_to
from models import Booking
from time_utils import start_of_week, timeslot_index

BOOTSTRAP_BLUE = "#0275d8"
BOOTSTRAP_GREEN = "#5cb85c"
BOOTSTRAP_LIGHT_BLUE = "#5bc0de"
BOOTSTRAP_ORANGE = "#f0ad4e"
BOOTSTRAP_YELLOW = "#f0e24e"
BOOTSTRAP_RED = "#d9534f"


def create_weekly_booking_map():

    all_bookings = [np.zeros(24 * 4) for _ in range(7)]
    weekly = defaultdict(lambda: [np.zeros(24 * 4) for _ in range(7)])
    booking_length = [0]*(24*4)

    for b in Booking.query.filter(Booking.start >= datetime(2020, 11, 8)).all():
        start = timeslot_index(b.start)
        end = timeslot_index(b.end)

        start_end_array = create_daily_from_to(start, end) * b.number
        all_bookings[b.start.weekday()] += start_end_array
        weekly[start_of_week(b.start)][b.start.weekday()] += start_end_array

        booking_length[end - start] += 1

    x = [[] for _ in range(7)]
    y = [[] for _ in range(7)]
    start = datetime(2020, 1, 1)
    for _, _data in weekly.items():
        for day in range(7):
            for time_idx, occupancy in enumerate(_data[day]):
                # print(time_idx, occupancy)
                x[day].append(start + timedelta(minutes=15 * time_idx))
                y[day].append(occupancy)

    return all_bookings, booking_length, x, y


def create_stats_layout(gym):
    all_bookings, booking_length, occ_x, occ_y = create_weekly_booking_map()
    start = datetime(2020, 1, 1)
    x = [start + timedelta(minutes=15 * x) for x in range(24*4)]

    days = [
        dbc.Col([
            dcc.Graph(
                figure={
                    "data": [
                        {
                            "x": x,
                            "y": all_bookings[_idx],
                            "type": "bar"
                        }
                    ],
                    "layout": {
                        "margin": {"t": 50, "r": 50, "l": 50, "b": 50},
                        "padding": {"t": 50, "r": 50, "l": 50, "b": 50}
                    }
                }
            )
        ], width=3) for _idx in range(7)
    ]

    days.append(
        dbc.Col([
            dcc.Graph(
                figure={
                    "data": [
                        {
                            "x": list(range(len(booking_length))),
                            "y": booking_length,
                            "type": "bar"
                        }
                    ],
                    "layout": {
                        "margin": {"t": 50, "r": 50, "l": 50, "b": 50},
                        "padding": {"t": 50, "r": 50, "l": 50, "b": 50}
                    }
                }
            )
        ], width=3)
    )

    days += [
        dbc.Col([
            dcc.Graph(
                figure={
                    "data": [
                        {
                            "x": occ_x[_idx],
                            "y": np.array(occ_y[_idx]),
                            "type": "histogram2d",
                            "nbinsx": 96,
                            "nbinsy": 40,
                        }
                    ],
                },

            )
        ], width=4) for _idx in range(7)
    ]

    return dbc.Row(days)