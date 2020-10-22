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


def is_admin():
    return current_user in get_chosen_gym().admins or current_user.role == "ADMIN"


def create_from_to(f, t):
    new_booking = np.zeros(24 * 4 * 7)
    for x in range(f, t):
        new_booking[x] += 1
    return new_booking


def get_bookings(d: date):
    all_bookings = np.zeros(24 * 4)
    my_bookings = np.zeros(24 * 4)
    nr_bookings_today = 0
    for b in Booking.query.filter(Booking.start >= d).filter(Booking.end <= d + timedelta(days=1)).all():
        start = (b.start - datetime(d.year, d.month, d.day)).seconds / 60 / 15
        end = (b.end - datetime(d.year, d.month, d.day)).seconds / 60 / 15

        start_end_array = create_from_to(int(start), int(end)) * b.number

        all_bookings += start_end_array

        if current_user and b.user.id == current_user.id:
            my_bookings += start_end_array
            nr_bookings_today += 1
    return np.array(all_bookings), np.array(my_bookings), nr_bookings_today


def create_rows(d, f, t):
    current, my_bookings, _ = get_bookings(d)

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
        return str(int(get_chosen_gym().max_people - current[row * config.COLUMNS * 4 + column]))

    rows = []
    dt = datetime(1, 1, 1)
    for x in range(config.ROWS):
        rows.append(
            html.Tr([
                html.Td(
                    html.Div([
                        html.Button(
                            get_text(x, k),
                            style={"background-color": get_color(x, k)},
                            id=dict(type="time-tile", column=k, row=x),
                            className="table-button"
                        ),
                    ], className="table-cell")
                )
                for k in range(config.COLUMNS * 4)
            ])
        )

        rows.append(
            html.Tr([
                html.Td(
                    html.Div([
                        (dt + timedelta(minutes=(x * config.COLUMNS * 4 + k * 4) * 15)).strftime("%H")
                    ], className="hour-cell")
                    , colSpan=4
                )
                for k in range(config.COLUMNS)
            ])
        )

    return rows


def create_popover():
    return html.Div([
        dbc.Button("Help", id="popover-target", color="primary"),
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
            placement="below"
        ),
    ])


@app.callback(
    [Output("main-graph", "figure"), Output("selection_store", "data"),
     Output("msg", "children"), Output("msg", "color"), Output("msg", "is_open"), Output("my-bookings", "children")],
    [Input("book", "n_clicks"),
     Input(dict(type="time-tile", column=ALL, row=ALL), "n_clicks"),
     Input('datepicker', 'date'), Input(dict(type="delete-booking", bookingid=ALL), "n_clicks"), Input('main-graph', 'clickData')],
    [State("selection_store", "data"), State("datepicker", "date"), State("nr_bookings", "value")]
)
def callback(book, k, dd, ff, lol, data, date, nr_bookings):

    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate
    d = datetime.strptime(date, "%Y-%m-%d")

    msg = ""
    msg_color = "danger"

    if trig.id == "clear":
        data = {"f": None, "t": None}
    elif trig.id == "book":

        # bookings, my_bookings, my_daily_bookings = get_bookings(d)

        if date is not None and data["f"] is not None and data["t"] is not None:

            b_start = datetime.strptime(data["f"], "%Y-%m-%dT%H:%M:%S")
            b_end = datetime.strptime(data["t"], "%Y-%m-%dT%H:%M:%S")


            # new_booking = create_from_to(data["f"], data["t"] + 1) * int(nr_bookings)
            #
            # total_nr_bookings = len([x.start for x in current_user.bookings if x.end >= datetime.now()])
            #
            # if np.any((bookings + new_booking) > get_chosen_gym().max_people):
            #     msg = "Booking interval is overlapping with a full time slot"
            # elif not is_admin() and np.any(np.logical_and(new_booking, my_bookings)):
            #     msg = "Booking interval is overlapping with a previous booking"
            # elif get_chosen_gym().max_booking_per_user_per_day is not None and \
            #         my_daily_bookings >= get_chosen_gym().max_booking_per_user_per_day:
            #     msg = "You can not book any more today"
            # elif get_chosen_gym().max_booking_per_user is not None and \
            #         total_nr_bookings >= get_chosen_gym().max_booking_per_user:
            #     msg = f"You can only have {get_chosen_gym().max_booking_per_user} active bookings"
            # else:
            db.session.add(Booking(start=b_start, end=b_end, user=current_user,
                                       gym=current_user.gyms[0], number=int(nr_bookings)))
            db.session.commit()
            data = {"f": None, "t": None}
        else:
            msg = "Invalid selection"
            msg_color = "danger"
    elif trig.id == "main-graph":
        picked_date = datetime.strptime(lol["points"][0]["x"].split(" ")[0] + " " + lol["points"][0]["y"], "%Y-%m-%d %H:%M")


        if data["f"] is not None and data["t"] is not None \
                or data["f"] is None:
            data["f"] = picked_date
            data["t"] = None
        elif data["t"] is None:
            # if get_chosen_gym().max_booking_length is not None and \
            #         (new_click - data["f"]) > (get_chosen_gym().max_booking_length - 1):
            #     data["t"] = data["f"] + (get_chosen_gym().max_booking_length - 1)
            #     msg = f"You can maximally choose {get_chosen_gym().max_booking_length} quarters"
            #     msg_color = "warning"
            # else:
            data["t"] = picked_date
    elif isinstance(trig.id, dict):
        if trig.id["type"] == "delete-booking":
            db.session.delete(db.session.query(Booking).filter_by(id=trig.id["bookingid"]).first())
            db.session.commit()

    return create_heatmap(d, data["f"], data["t"]), data, msg, msg_color, msg != "", create_bookings()


def as_date(k):
    if isinstance(k, datetime):
        return k
    else:
        return datetime.strptime(k, "%Y-%m-%dT%H:%M:%S")


def create_bookings():
    k = defaultdict(list)

    for x in current_user.bookings:
        if x.end >= datetime.now():
            k[x.start.date()].append(x)

    result = []
    for d in sorted(k.keys()):
        result.append(
            html.Tr([
                html.Td(d.strftime("%d %b %Y"), style={"background-color": "lightgrey"}, colSpan=3),
                html.Td("#", style={"background-color": "lightgrey"}, colSpan=2),
            ])
        )
        for b in k[d]:
            result.append(
                html.Tr([
                    html.Td(b.start.strftime("%H:%M"), style={"text-align": "left"}),
                    html.Td("-", style={"text-align": "left"}),
                    html.Td(b.end.strftime("%H:%M"), style={"text-align": "left"}),
                    html.Td(b.number if b.number > 1 else "", style={"text-align": "left"}),
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
    [Output("redirect", "children"), Output("gym-err", "children"), Output("gym-err", "is_open")],
    [Input("add_gym", "n_clicks")],
    [State("gym_code", "value")]
)
def on_new_gym(n, gym_code):

    if gym_code is not None:
        g = db.session.query(Gym).filter_by(code=gym_code).first()
        if g:
            current_user.gyms.append(g)
            db.session.commit()
            return dcc.Location(pathname="/", id="someid_doesnt_matter"), "", False

    return "", "Gym not found", n is not None


@app.callback(
    [Output("layout", "children"), Output("navbar", "children"), Output("navbar", "brand")],
    [Input("location", "pathname")]
)
def path(url):

    navbar_items = [
        dbc.NavItem(create_popover()),
        dbc.NavItem(dcc.LogoutButton("Logout", logout_url="/user/sign-out", className="btn btn-primary"))
    ]

    if len(current_user.gyms) == 0:
        layout = dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H3("Please enter gym code", className="my-3"),
                    dbc.InputGroup([dbc.Input(id="gym_code")], className="mb-2"),
                    dbc.Button("OK", id="add_gym", color="primary", className="mb-2"),
                    dbc.Alert(id="gym-err", is_open=False, color="danger")
                ], width=4)
            ], justify="around"),
            dbc.Row([

            ])
        ], fluid=True)
        txt = f"{current_user.username}"
    else:
        layout = create_main_layout()
        txt = f"{current_user.username} @ {get_chosen_gym().name}"
    return layout, navbar_items, txt


import plotly.graph_objects as go


def create_heatmap(d, f, t):

    week_start_day = d - timedelta(days=d.weekday() % 7)

    all_bookings = np.zeros(24 * 4 * 7)
    my_bookings = np.zeros(24 * 4 * 7)
    nr_bookings_today = 0
    for b in Booking.query.filter(Booking.start >= week_start_day).filter(Booking.end <= week_start_day + timedelta(days=8)).all():
        start = (b.start - datetime(week_start_day.year, week_start_day.month, week_start_day.day)).total_seconds() / 60 / 15
        end = (b.end - datetime(week_start_day.year, week_start_day.month, week_start_day.day)).total_seconds() / 60 / 15

        start_end_array = create_from_to(int(start), int(end)) * b.number

        all_bookings += start_end_array

        if current_user and b.user.id == current_user.id:
            my_bookings += start_end_array
            nr_bookings_today += 1

    x = [(week_start_day.date() + timedelta(days=x)) for x in range(7)]
    start = datetime(1, 1, 1)
    y = [(start + timedelta(minutes=15*k)).strftime("%H:%M") for k in range(24*4)]

    all_bookings[my_bookings > 0] = -3

    if f:
        start = (as_date(f) - datetime(week_start_day.year, week_start_day.month,
                                    week_start_day.day)).total_seconds() / 60 / 15
        all_bookings[int(start)] = -3.5
    if t:
        end = (as_date(t) - datetime(week_start_day.year, week_start_day.month,
                                    week_start_day.day)).total_seconds() / 60 / 15
        for _x in range(int(start)+1, int(end)):

            all_bookings[_x] = -3.5

    if week_start_day < datetime.now() < week_start_day + timedelta(days=8):
        start = (datetime.now() - datetime(week_start_day.year, week_start_day.month,
                                    week_start_day.day)).total_seconds() / 60 / 15

        all_bookings[:int(start)+1] = -4.5

    z = np.reshape(all_bookings, (7, 24*4)).transpose()

    _max = get_chosen_gym().max_people
    _close = _max - config.CLOSE
    l = _max + 5

    fig = go.Figure(
        layout=go.Layout(margin=dict(t=0)),
        data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            hoverongaps=False,
            zmin=-5,
            zmax=_max,
            # showscale=False,
            colorscale=[
                (0.0, "grey"), (1 / l, "grey"),
                (1/l, "yellow"), (2 / l, "yellow"),
                (2 / l, "green"), (5 / l, "green"),
                (5 / l, "blue"), ((_close + 5) / l, "blue"),
                ((_close + 5) / l, "orange"), (0.99, "orange"), (1.0, "red"),
            ]
        )
    )
    return fig


def create_main_layout():
    return dbc.Row([
        dbc.Col([

        ], xs=0, sm=2),
        dbc.Col([
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Choose day"),
                        dcc.DatePickerSingle(
                            id="datepicker",
                            date=datetime.now().date(),
                            min_date_allowed=datetime.now().date(),
                            max_date_allowed=datetime.now().date() + timedelta(days=14) if not is_admin() else None,
                            className="m-1",
                            display_format='DD MMM YYYY'
                        ),
                    ]),

                ], justify="between", className="my-3"),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            dcc.Graph(id="main-graph", style={"height": "70vh", "width": "100%"})
                            # html.Table(id="main-table",
                            #            style={"border-collapse": "collapse",
                            #                   "width": "100%"})
                        ], className="my-3"),
                    ], width=12),
                ], justify="between"),
                dbc.Row([
                    dbc.Alert(id="msg", is_open=False),
                    html.Div(dbc.Input(value=1, id="nr_bookings"),
                             hidden=not is_admin()),
                    dbc.Button("Book", id="book", color="success")
                ], justify="end")
            ], fluid=True)
        ], width=12, xs=7),
        dbc.Col([
            dbc.Row([dbc.Label("My bookings", className="m-3")]),
            dbc.Row(id="my-bookings")
        ], width=12, xs=3)
    ])


app.layout = html.Div([
    dcc.Store(id="selection_store", data={"f": None, "t": None}),
    dcc.Store(id="bookings_store", data={}),
    dcc.Location(id="location"),
    html.Div(id="redirect"),
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
