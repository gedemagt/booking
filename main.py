from collections import defaultdict
from datetime import datetime, timedelta, date

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import ALL
from dash_extensions.enrich import Output, Input, State, Trigger
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered
from flask_login import current_user
import plotly.graph_objects as go

import numpy as np

import config
from admin import init_flask_admin
from app import app
from booking_logic import create_from_to, validate_booking
from components import create_popover
from models import Booking, db, Gym
from time_utils import start_of_week, start_of_day
from utils import get_chosen_gym, is_admin


def create_from_to_day(f, t, n=1):
    new_booking = np.zeros(24 * 4)
    for x in range(f, t):
        new_booking[x] += n
    return new_booking


def parse(s):
    if s is None:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def parse_heatmap_click(data):
    return datetime.strptime(data["points"][0]["x"].split(" ")[0] + " " + data["points"][0]["y"], "%Y-%m-%d %H:%M")


@app.callback(
    [Output("my-bookings", "children"), Output("main-graph", "figure")],
    [Input("bookings_store", "data"), Input("selection_store", "data")], group="redraw")
def redraw_all(data1, data):

    d = parse(data["d"])
    return create_bookings(), create_heatmap(d, parse(data["f"]), parse(data["t"]))


@app.callback(
    Output("bookings_store", "data"),
    Trigger(dict(type="delete-booking", bookingid=ALL), "n_clicks")
)
def on_delete():
    trig = get_triggered()
    if trig.id is not None and trig.n_clicks is not None:
        try:
            db.session.delete(db.session.query(Booking).filter_by(id=trig.id["bookingid"]).first())
            db.session.commit()
            return {"deleted": trig.id["bookingid"]}
        except Exception as e:
            import traceback
            traceback.print_exc()
    raise PreventUpdate


@app.callback(
    [Output("msg", "children"), Output("msg", "color"),
     Output("msg", "is_open"), Output("selection_store", "data")],
    [Trigger("book", "n_clicks")],
    [State("selection_store", "data"), State("nr_bookings", "value")], group="ok"
)
def on_booking(data, nr_bookings):
    msg = ""
    msg_color = "warning"
    if date is not None and data["f"] is not None and data["t"] is not None:

        b_start = datetime.strptime(data["f"], "%Y-%m-%dT%H:%M:%S")
        b_end = datetime.strptime(data["t"], "%Y-%m-%dT%H:%M:%S")

        try:
            validate_booking(b_start, b_end, int(nr_bookings))
            db.session.add(Booking(start=b_start, end=b_end, user=current_user,
                                   gym=current_user.gyms[0], number=int(nr_bookings)))
            db.session.commit()
            msg = "Success"
            msg_color = "success"
        except AssertionError as e:
            msg = str(e)
            msg_color = "danger"
        except Exception:
            import traceback
            traceback.print_exc()

        data["f"] = None
        data["t"] = None
    else:
        msg = "Invalid selection"
        msg_color = "danger"

    return msg, msg_color, True, data


@app.callback(
    [Output("selection_store", "data"), Output("week", "children")],
    [Trigger("prev_week", "n_clicks"), Trigger("next_week", "n_clicks")],
    [State("selection_store", "data")], group="ok"
)
def on_week(data):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    d = parse(data["d"])

    if trig.id == "next_week":
        data["d"] = d = d + timedelta(days=7)
    if trig.id == "prev_week":
        if datetime.now() < d:
            data["d"] = d - timedelta(days=7)
    return data, d.isocalendar()[1]


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
                    html.Td(b.number, style={"text-align": "left"}),
                    html.Td(dbc.Button("Delete", id=dict(type="delete-booking", bookingid=b.id), color="danger"))
                ]),
            )
    return dbc.Table(result, style={"width": "100%"})


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
    [Trigger("location", "pathname")]
)
def path():
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


def create_heatmap(d, f, t):
    week_start_day = start_of_week(d)

    all_bookings = np.zeros(24 * 4 * 7)
    my_bookings = np.zeros(24 * 4 * 7)
    nr_bookings_today = 0
    for b in Booking.query.filter(Booking.start >= week_start_day).filter(
            Booking.end <= week_start_day + timedelta(days=8)).all():
        start = (b.start - datetime(week_start_day.year, week_start_day.month,
                                    week_start_day.day)).total_seconds() / 60 / 15
        end = (b.end - datetime(week_start_day.year, week_start_day.month,
                                week_start_day.day)).total_seconds() / 60 / 15

        start_end_array = create_from_to(int(start), int(end)) * b.number

        all_bookings += start_end_array

        if current_user and b.user.id == current_user.id:
            my_bookings += start_end_array
            nr_bookings_today += 1

    x = [(week_start_day.date() + timedelta(days=x)) for x in range(7)]
    start = datetime(1, 1, 1)
    y = [(start + timedelta(minutes=15 * k)).strftime("%H:%M") for k in range(24 * 4)]

    all_bookings[my_bookings > 0] = -3

    start_idx = 0
    if f:
        start_idx = (as_date(f) - datetime(week_start_day.year, week_start_day.month,
                                       week_start_day.day)).total_seconds() / 60 / 15
        all_bookings[int(start_idx)] = -3.5
    if t:
        end_idx = (as_date(t) - datetime(week_start_day.year, week_start_day.month,
                                     week_start_day.day)).total_seconds() / 60 / 15
        for _x in range(int(start_idx) + 1, int(end_idx)):
            all_bookings[_x] = -3.5

    if week_start_day < datetime.now() < week_start_day + timedelta(days=8):
        start = (datetime.now() - datetime(week_start_day.year, week_start_day.month,
                                           week_start_day.day)).total_seconds() / 60 / 15

        all_bookings[:int(start) + 1] = -4.5

    z = np.reshape(all_bookings, (7, 24 * 4)).transpose()

    _max = get_chosen_gym().max_people
    _close = _max - config.CLOSE
    l = _max + 5

    fig = go.Figure(
        layout=go.Layout(
            margin=dict(t=0, r=0, l=0, b=0),
            xaxis=dict(fixedrange=True, mirror="allticks", side="top", tickfont=dict(size=20)),
            yaxis=dict(fixedrange=True, autorange="reversed"),

        ),
        data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            hoverongaps=False,
            zmin=-5,
            zmax=_max,
            showscale=False,
            xgap=5,
            ygap=0.1,
            colorscale=[
                (0.0, "grey"), (1 / l, "grey"),
                (1 / l, "yellow"), (2 / l, "yellow"),
                (2 / l, "green"), (5 / l, "green"),
                (5 / l, "blue"), ((_close + 5) / l, "blue"),
                ((_close + 5) / l, "orange"), (0.99, "orange"), (1.0, "red"),
            ]
        )
    )

    fig.update_layout(
        yaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=8
        )
    )

    fig.update_layout(
        xaxis_tickformat='%a %d %b'
    )

    return fig


OPTIONS = [{'label': (datetime(1, 1, 1) + timedelta(minutes=15 * x)).strftime("%H:%M"), 'value': x} for x in
           range(24 * 4)]


@app.callback(
    [Output("selection_store", "data")],
    [Input("from-drop-down", "value"), Input("to-drop-down", "value"),
     Input('main-graph', 'clickData'), Input("date-picker", "date")],
    [State("selection_store", "data")], group="ok"
)
def on_chosen_from(prev_from, prev_to, click, date_picker_date, data):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    if trig.id == "main-graph" and click:
        picked_date = parse_heatmap_click(click)
        if data["f"] is not None and data["t"] is not None \
                or data["f"] is None:
            data["f"] = picked_date
            data["t"] = None
        elif data["t"] is None:
            f = parse(data["f"])
            data["f"] = min(f, picked_date)
            data["t"] = max(f, picked_date)
        data["source"] = "graph"
    else:
        if trig.id == "from-drop-down":
            if prev_from is None:
                data["f"] = None
                data["t"] = None
            else:
                data["f"] = date_picker_date + "T" + OPTIONS[prev_from]["label"] + ":00"
        elif trig.id == "to-drop-down":
            if prev_to is None:
                data["t"] = None
            else:
                data["t"] = date_picker_date + "T" + OPTIONS[prev_to]["label"] + ":00"
        elif trig.id == "date-picker":
            if "t" in data:
                data["t"] = str(date_picker_date) + "T" + data["t"].split("T")[-1]
            if "f" in data:
                data["f"] = str(date_picker_date) + "T" + data["f"].split("T")[-1]
        data["source"] = "input"
    return data


@app.callback(
    [Output("from-drop-down", "value"), Output("to-drop-down", "options"),
     Output("to-drop-down", "value"), Output("date-picker", "date")],
    [Input("selection_store", "data")],
    [State("from-drop-down", "value"), State("to-drop-down", "options"),
     State("to-drop-down", "value"), State("date-picker", "date")]
)
def update_inputs(data, prev_from, prev_options, prev_to, prev_date):
    from_value = None
    to_value = None
    date = start_of_day(datetime.now())

    if data.get("source", "") == "graph":
        if data["f"] is not None:
            d = parse(data["f"])
            date = start_of_day(d)
            from_value = int((d - start_of_day(d)).total_seconds() / 60 / 15)
        if data["t"] is not None:
            d = parse(data["t"])
            to_value = int((d - start_of_day(d)).total_seconds() / 60 / 15)

        return from_value, OPTIONS[from_value + 1:] if from_value else OPTIONS[1:], to_value, date.date()
    elif data.get("source", "") == "input":
        return prev_from if data["f"] is not None else None, \
               prev_options , \
               prev_to if data["t"] is not None else None, prev_date
    else:
        raise PreventUpdate


def create_main_layout():
    return dbc.Row([
        dbc.Col([

        ], xs=0, sm=2),
        dbc.Col([
            dbc.Container([
                dbc.Row([

                ], justify="end"),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            dbc.Button("<", id="prev_week", color="primary"),
                            html.Span([
                                html.Span("Week", className="ml-3 mr-1"),
                                html.Span(id="week", className="mr-3 ml-1"),
                            ]),
                            dbc.Button(">", id="next_week", color="primary")
                        ], style={"text-align": "center"})
                    ], width=12),

                ], justify="between", className="my-3 mr-2"),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            dcc.Graph(id="main-graph", style={"height": "70vh", "width": "100%"})
                        ], className="my-3"),
                    ], width=12),
                ], justify="between"),
                dbc.Row([
                    dbc.Alert(id="msg", is_open=False)
                ], justify="end"),
            ], fluid=True)
        ], width=12, xs=7),
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("New booking"),
                        dbc.CardBody([
                            html.Table([
                                html.Tr([
                                    html.Td([
                                        "#"
                                    ]),
                                    html.Td([
                                        html.Div(
                                            dbc.Input(
                                                value=1,
                                                id="nr_bookings",
                                                type="number",
                                                min=1,
                                                max=get_chosen_gym().max_number_per_booking if not is_admin() else get_chosen_gym().max_people
                                            ), style={"width": "100%"}
                                        )
                                    ]),

                                ]),
                                html.Tr([
                                    html.Td([
                                        "Day"
                                    ]),
                                    html.Td([
                                        dcc.DatePickerSingle(
                                            id="date-picker",
                                            date=datetime.now().date(),
                                            min_date_allowed=datetime.now().date(),
                                        )
                                    ])
                                ]),
                                html.Tr([
                                    html.Td([
                                        "Start"
                                    ]),
                                    html.Td([
                                        dcc.Dropdown(
                                            id="from-drop-down",
                                            value=4 * 8,
                                            options=OPTIONS[:-1]
                                        )
                                    ])
                                ]),
                                html.Tr([
                                    html.Td([
                                        "Stop"
                                    ]),
                                    html.Td([
                                        dcc.Dropdown(
                                            id="to-drop-down",
                                            options=OPTIONS[:-1]
                                        )
                                    ])
                                ]),
                            ])
                        ]),
                        dbc.CardFooter([
                            dbc.Button("Book", id="book", color="success")
                        ])
                    ])
                ], width=12)
            ]),
            dbc.Card([
                dbc.CardHeader("My bookings"),
                dbc.CardBody([
                    html.Div(id="my-bookings")
                ])
            ], className="my-3")
        ], width=12, xs=3)
    ], className="p-3")


app.layout = html.Div([
    dcc.Store(id="selection_store", data={"f": None, "t": None, "d": start_of_week(), "source": None}),
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
    app.run_server(debug=False, dev_tools_ui=False)
