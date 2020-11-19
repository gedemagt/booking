from datetime import timedelta

import dash_html_components as html
import humanize
from dash.dependencies import Output, State, Input

from app import app





def create_gym_info(gym):
    rows = [
        html.Tr([
            html.Td("Capacity", className="font-weight-bold"),
            html.Td(gym.get_max_people(gym.zones[0].id)) if len(gym.zones) == 1 else None
        ])
    ]
    if len(gym.zones) > 1:
        for zone in gym.zones:
            rows.append(
                html.Tr([
                    html.Td(zone.name, className="pl-3"),
                    html.Td(gym.get_max_people(zone.id))
                ]),
            )

    return html.Table(
        rows +
        [
            html.Tr([
                html.Td("Length of booking", className="pr-3 font-weight-bold"),
                html.Td(humanize.naturaldelta(timedelta(minutes=15*gym.max_booking_length)))
            ]) if gym.max_booking_length else None,
            html.Tr([
                html.Td("Active bookings", className="pr-3 font-weight-bold"),
                html.Td(f"{gym.max_booking_per_user}" + ("*" if gym.book_before else ""))
            ]) if gym.max_booking_per_user else None,
            html.Tr([
                html.Td("Persons per booking", className="pr-3 font-weight-bold"),
                html.Td(gym.max_number_per_booking)
            ]) if gym.max_number_per_booking else None,
            html.Tr([
                html.Td("Booking horizon", className="pr-3 font-weight-bold"),
                html.Td(humanize.naturaldelta(timedelta(days=gym.max_days_ahead)))
            ]) if gym.max_number_per_booking else None,
            html.Tr([
                html.Td(f"* A booking counts as active until {humanize.naturaldelta(timedelta(minutes=15*gym.book_before))} before it ends", className="pr-3", colSpan=2),
            ]) if gym.book_before else None
        ]
    )
