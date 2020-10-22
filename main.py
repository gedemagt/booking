from collections import defaultdict
from datetime import datetime, timedelta, date

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, ALL, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered
from flask_login import current_user

import numpy as np

import config
from admin import init_flask_admin
from app import app
from models import Booking, db, Gym


def get_chosen_gym():
    return current_user.gyms[0]


def create_from_to(f, t):
    new_booking = np.zeros(24 * 4)
    for x in range(f, t):
        new_booking[x] += 1
    return new_booking


def get_bookings(d: date):
    all_bookings = np.zeros(24 * 4)
    my_bookings = np.zeros(24 * 4)
    for b in Booking.query.filter(Booking.start >= d).filter(Booking.end <= d + timedelta(days=1)).all():
        start = (b.start - datetime(d.year, d.month, d.day)).seconds / 60 / 15
        end = (b.end - datetime(d.year, d.month, d.day)).seconds / 60 / 15

        start_end_array = create_from_to(int(start), int(end)) * b.number

        all_bookings += start_end_array

        if current_user and b.user.id == current_user.id:
            my_bookings += start_end_array
    return np.array(all_bookings), np.array(my_bookings)


def create_rows(d, f, t):
    current, my_bookings = get_bookings(d)

    def selected(row, column):
        if f is None:
            return False
        elif t is None:
            return f == row * config.COLUMNS * 4 + column
        else:
            return f <= row * config.COLUMNS * 4 + column <= t

    def is_available(row, column):
        return current[row * config.COLUMNS * 4 + column] < get_chosen_gym().max_people

    def is_close(row, column):
        return (get_chosen_gym().max_people - config.CLOSE) <= current[row * config.COLUMNS * 4 + column] < get_chosen_gym().max_people

    def is_yours(row, column):
        return my_bookings[row * config.COLUMNS * 4 + column] > 0

    def get_color(row, column):
        if selected(row, column):
            return "grey"
        elif is_yours(row, column):
            return "green"
        elif is_close(row, column):
            return "orange"
        elif is_available(row, column):
            return "blue"
        else:
            return "red"

    def get_text(row, column):
        if is_yours(row, column):
            return ""
        elif is_close(row, column):
            return str(int(get_chosen_gym().max_people - current[row * config.COLUMNS * 4 + column]))
        else:
            return ""

    rows = []
    dt = datetime(1, 1, 1)
    for x in range(config.ROWS):
        rows.append(
            html.Tr([
                html.Td(
                    html.Button(
                        get_text(x, k),
                        style={"width": "100%", "height": "45px", "border": "none",
                               "background-color": get_color(x, k), "color": "white",
                               "font-weight": "bold"},
                        id=dict(type="time-tile", column=k, row=x)
                    ),
                    style={"text-align": "center"}
                )
                for k in range(config.COLUMNS * 4)
            ])
        )
        rows.append(
            html.Tr([
                html.Td(
                    (dt + timedelta(minutes=(x * config.COLUMNS * 4 + k) * 15)).strftime("%H:%M")
                    if (x * config.COLUMNS * 4 + k) % 4 == 0 else "",
                    colSpan=2
                )
                for k in range(config.COLUMNS * 2)
            ])
        )

    return rows


def create_popover():
    return html.Div([
        html.Button("?",
                    id="popover-target",
                    style={"width": "38px", "height": "38px", "background-color": "white",
                           "border": "none", "text-align": "center"}),
        dbc.Popover(
            [
                dbc.PopoverBody(
                    html.Table([
                        html.Tr([
                            html.Td([
                                "Available"
                            ], className="p-1",
                                style={"background-color": "blue", "color": "white", "font-weight": "bold"}),
                        ]),
                        html.Tr([
                            html.Td([
                                "Booked"
                            ], className="p-1",
                                style={"background-color": "green", "color": "white", "font-weight": "bold"}),

                        ]),
                        html.Tr([
                            html.Td([
                                "Almost full"
                            ], className="p-1",
                                style={"background-color": "orange", "color": "white", "font-weight": "bold"}),
                        ]),
                        html.Tr([
                            html.Td([
                                "Full"
                            ], className="p-1",
                                style={"background-color": "Red", "color": "white", "font-weight": "bold"}),
                        ]),
                        html.Tr([
                            html.Td([
                                "Selected"
                            ], className="p-1",
                                style={"background-color": "grey", "color": "white", "font-weight": "bold"}),
                        ])
                    ])
                ),
            ],
            id="popover",
            is_open=False,
            target="popover-target",
            placement="left"
        ),
    ])


@app.callback(
    [Output("main-table", "children"), Output("selection_store", "data"),
     Output("msg", "children"), Output("msg", "color"), Output("msg", "is_open"), Output("my-bookings", "children")],
    [Input("book", "n_clicks"),
     Input(dict(type="time-tile", column=ALL, row=ALL), "n_clicks"),
     Input('datepicker', 'date'), Input(dict(type="delete-booking", bookingid=ALL), "n_clicks")],
    [State("selection_store", "data"), State("datepicker", "date")]
)
def callback(book, k, dd, ff, data, date):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    d = datetime.strptime(date, "%Y-%m-%d")

    msg = ""
    msg_color = "danger"

    if trig.id == "clear":
        data = {"f": None, "t": None}
    elif trig.id == "book":

        bookings, my_bookings = get_bookings(d)

        if date is not None and data["f"] is not None and data["t"] is not None:

            b_start = d + timedelta(minutes=15 * data["f"])
            b_end = d + timedelta(minutes=15 * (data["t"] + 1))

            new_booking = create_from_to(data["f"], data["t"] + 1)

            if np.any((bookings + new_booking) > get_chosen_gym().max_people):
                msg = "Booking interval is overlapping with a full time slot"
            elif np.any((new_booking + my_bookings) > 1):
                msg = "Booking interval is overlapping with a previous booking"
            else:
                db.session.add(Booking(start=b_start, end=b_end, user=current_user, gym=current_user.gyms[0]))
                db.session.commit()
            data = {"f": None, "t": None}
        else:
            msg = "Invalid selection"
            msg_color = "danger"
    elif isinstance(trig.id, dict):
        if trig.id["type"] == "time-tile":
            new_click = trig.id["row"] * config.COLUMNS * 4 + trig.id["column"]
            if data["f"] is not None and data["t"] is not None\
                    or data["f"] is None:
                data["f"] = new_click
                data["t"] = None
            elif data["t"] is None:
                if get_chosen_gym().max_booking_length is not None and \
                        (new_click - data["f"]) > (get_chosen_gym().max_booking_length - 1):
                    data["t"] = data["f"] + (get_chosen_gym().max_booking_length - 1)
                    msg = f"You can maximally choose {get_chosen_gym().max_booking_length} quarters"
                    msg_color = "warning"
                else:
                    data["t"] = new_click
        elif trig.id["type"] == "delete-booking":
            db.session.delete(db.session.query(Booking).filter_by(id=trig.id["bookingid"]).first())
            db.session.commit()

    return create_rows(d, data["f"], data["t"]), data, msg, msg_color, msg != "", create_bookings()


def create_bookings():
    k = defaultdict(list)

    for x in current_user.bookings:
        k[x.start.date()].append(x)

    result = []
    for d in sorted(k.keys()):
        result.append(
            html.Tr([
                html.Td(d.strftime("%d %b %Y"), style={"background-color": "lightgrey"}, colSpan=4)
            ])
        )
        for b in k[d]:
            result.append(
                html.Tr([
                    html.Td(b.start.strftime("%H:%M"), style={"text-align": "left"}),
                    html.Td("-", style={"text-align": "left"}),
                    html.Td(b.end.strftime("%H:%M"), style={"text-align": "left"}),
                    html.Td(dbc.Button("Delete", id=dict(type="delete-booking", bookingid=b.id), color="danger"))
                ]),
            )
    return dbc.Table(result, style={"width": "200px"})


@app.callback(
    Output("popover", "is_open"),
    [Input("popover-target", "n_clicks")],
    [State("popover", "is_open")],
)
def toggle_popover(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(
    [Output("redirect", "children")],
    [Input("add_gym", "n_clicks")],
    [State("gym_code", "value")]
)
def on_new_gym(n, gym_code):

    if gym_code is not None:
        g = db.session.query(Gym).filter_by(code=gym_code).first()
        if g:
            current_user.gyms.append(g)
            db.session.commit()
            return dcc.Location(pathname="/", id="someid_doesnt_matter"),

    raise PreventUpdate


@app.callback(
    [Output("layout", "children"), Output("navbar", "children")],
    [Input("location", "pathname")]
)
def path(url):

    navbar_items = [
        dbc.NavItem(dcc.LogoutButton("Logout", logout_url="/user/sign-out", className="btn btn-primary"))
    ]

    if len(current_user.gyms) == 0:
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H3("Please enter gym code"),
                    dbc.InputGroup([dbc.Input(id="gym_code")]),
                    dbc.Button("OK", id="add_gym", color="primary"),
                ], width=4)
            ], justify="around"),
            dbc.Row([

            ])
        ], fluid=True), navbar_items

    return create_main_layout(), navbar_items


def create_main_layout():
    return dbc.Row([
        dbc.Col([

        ], width=2),
        dbc.Col([
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Choose day"),
                        dcc.DatePickerSingle(
                            id="datepicker",
                            date=datetime.now().date(),
                            min_date_allowed=datetime.now().date(),
                            max_date_allowed=datetime.now().date() + timedelta(days=14),
                            className="m-1",
                            display_format='DD MMM YYYY'
                        ),
                    ]),

                ], justify="between", className="my-3"),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Table(id="main-table",
                                       style={"border-collapse": "collapse",
                                              "width": "100%"})
                        ], className="my-3"),
                    ], width=10),
                    dbc.Col([
                        html.Div(style={"height": "10px"}),
                        create_popover(),
                        html.Div(style={"height": "315px"}),
                        dbc.Button("Book", id="book", color="success")
                    ], width=2)
                ], justify="between"),
                dbc.Row([
                    dbc.Alert(id="msg", is_open=False),

                ], justify="end")
            ], fluid=True)
        ], width=7),
        dbc.Col([
            dbc.Row([dbc.Label("My bookings", className="m-3")]),
            dbc.Row(id="my-bookings")
        ], width=3)
    ])


app.layout = html.Div([
    dcc.Store(id="selection_store", data={"f": None, "t": None}),
    dcc.Store(id="bookings_store", data={}),
    dcc.Location(id="location"),
    html.Div(id="redirect", style={"hidden": True}),
    dbc.NavbarSimple(
        children=[],
        brand="Booking",
        color="primary",
        dark=True,
        id="navbar"
    ),
    html.Div(id="layout")
])


if __name__ == '__main__':
    init_flask_admin()
    app.suppress_callback_exceptions = True
    app.run_server(debug=True, dev_tools_ui=False)
