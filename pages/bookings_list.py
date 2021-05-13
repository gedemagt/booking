from collections import defaultdict
from datetime import datetime
from typing import Union

import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import ALL
from dash_extensions.enrich import Output, State, Trigger
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered
from flask_login import current_user

from app import app
from models import Booking, db, RepeatingBooking
from utils import get_chosen_gym, is_admin, is_instructor


BOOKING_TYPES = {
    Booking.__name__: Booking,
    RepeatingBooking.__name__: RepeatingBooking
}


REPEAT_DESCRIPTION = {
    "w": "Weekly"
}


def create_single_booking(b: Union[Booking, RepeatingBooking]):
    result = []
    result.append(dbc.Row([
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    f'{b.start.strftime("%H:%M")} - {b.end.strftime("%H:%M")}',
                ], width=12),
                dbc.Col([
                    b.zone.name if len(get_chosen_gym().zones) > 1 else "",
                ], width=12),
                dbc.Col([
                    f"{REPEAT_DESCRIPTION[b.repeat]}: {b.start:%A}",
                ], width=12) if isinstance(b, RepeatingBooking) else None
            ])
        ], width=6),
        dbc.Col([
            b.number,
        ], width=2),
        dbc.Col([
            dbc.Row([
                html.Div([
                    html.Span(
                        dbc.Button(
                            html.I(className="fa fa-sticky-note"),
                            id=dict(type="add-note", bookingid=b.id, bookingtype=b.__class__.__name__),
                            color="primary",
                            size="sm",
                            className="mr-1"
                        ),
                        title=b.note
                    ),
                ]) if (is_admin() or is_instructor()) and b.note is None else None,
                dbc.Button(html.I(className="fa fa-trash"), id=dict(type="delete-booking", bookingid=b.id, bookingtype=b.__class__.__name__),
                           color="danger", size="sm")
            ], justify="end")
        ], width=3)
    ], className="my-1"))

    if is_admin() or is_instructor():
        if b.note:
            result.append(dbc.Row([
                dbc.Col(html.Div(
                    [
                        html.Div(
                            b.note,
                            className="p-1",
                        ),
                        dbc.Row([
                            dbc.Col([
                                html.Span(html.Button(
                                    "Delete",
                                    className="link-btn",
                                    id=dict(type="delete-note", bookingid=b.id, bookingtype=b.__class__.__name__)
                                ), className="float-right mr-1"),
                                html.Span(html.Button(
                                    "Edit",
                                    className="link-btn",
                                    id=dict(type="edit-note", bookingid=b.id, bookingtype=b.__class__.__name__)
                                ), className="float-right  mr-3")
                            ])
                        ], justify="end")
                    ],
                    style={"background-color": "#ffffc2"}
                ), width=12)
            ]))
    return html.Div(result)


def create_bookings(bookings):
    k = defaultdict(list)

    for x in bookings:
        if x.end >= datetime.now():
            k[x.start.date()].append(x)

    result = []
    for d in sorted(k.keys()):
        result.append(
            dbc.Row([
                dbc.Col(d.strftime("%d %b %Y"), width=6),
                dbc.Col("#", width=2)
            ], style={"background-color": "lightgrey"}, className="mt-2")
        )

        for b in k[d]:
            result.append(create_single_booking(b))

            result.append(html.Hr())
        result.pop(-1)
    return dbc.Container([
        dbc.Table(result, style={"width": "100%"})
    ], fluid=True)


@app.callback(
    [Output("edit-booking-modal", "is_open"), Output("b-edit-id", "children"),
     Output("b-edit-type", "children"), Output("booking-note-input", "value")],
    [Trigger(dict(type="add-note", bookingid=ALL, bookingtype=ALL), "n_clicks"),
     Trigger(dict(type="edit-note", bookingid=ALL, bookingtype=ALL), "n_clicks"),
     Trigger("ok-edit-booking", "n_clicks")],
    [State("b-edit-id", "children"), State("b-edit-type", "children"), State("booking-note-input", "value")],
)
def toggle_modal2(bid, b_type, note):

    t = get_triggered()

    if isinstance(t.id, dict) and get_triggered().n_clicks is not None:
        new_bid = int(t.id["bookingid"])
        b = BOOKING_TYPES[t.id["bookingtype"]].query.filter_by(id=new_bid).first()

        return True, new_bid, t.id["bookingtype"], b.note
    elif t.id == "ok-edit-booking":
        b = BOOKING_TYPES[b_type].query.filter_by(id=int(bid)).first()
        if note and note.strip():
            b.note = note
            db.session.add(b)
            db.session.commit()
        return False, None, "", ""
    return False, None, "", ""


@app.callback(
    Output("bookings_store", "data"),
    [
        Trigger(dict(type="delete-booking", bookingid=ALL, bookingtype=ALL), "n_clicks"),
        Trigger(dict(type="delete-note", bookingid=ALL, bookingtype=ALL), "n_clicks")
    ]
)
def on_delete():
    trig = get_triggered()
    if trig.id is not None and trig.n_clicks is not None:
        if trig.id["type"] == "delete-booking":
            try:
                db.session.delete(
                    db.session.query(BOOKING_TYPES[trig.id["bookingtype"]]).filter_by(id=trig.id["bookingid"]).first())
                db.session.commit()
                return {"deleted": trig.id["bookingid"]}
            except Exception as e:
                import traceback
                traceback.print_exc()
        if trig.id["type"] == "delete-note":
            bid = trig.id["bookingid"]
            booking = db.session.query(BOOKING_TYPES[trig.id["bookingtype"]]).filter_by(id=bid).first()
            booking.note = None
            db.session.add(booking)
            db.session.commit()
            return {"deleted_note": trig.id["bookingid"], "bookingtype": trig.id["bookingtype"]}
    raise PreventUpdate


@app.callback(
    Output("my-bookings", "children"),
    [Trigger("data-store", "data"), Trigger("bookings_store", "data"), Trigger("edit-booking-modal", "is_open")]
     )
def redraw_all_user():
    return create_bookings(current_user.bookings)


@app.callback(
    Output("gym-bookings", "children"),
    [Trigger("data-store", "data"), Trigger("bookings_store", "data"), Trigger("edit-booking-modal", "is_open")]
)
def redraw_all_repeating():
    bookings = []
    for z in get_chosen_gym().zones:
        bookings += z.repeating_bookings
    return create_bookings(bookings)


my_bookings_list = html.Div(id="my-bookings")
gym_bookings_list = html.Div(id="gym-bookings")
