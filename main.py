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
from booking_logic import validate_booking, create_weekly_booking_map
from components import create_popover
from gymadmin import create_gym_admin_layout
from models import Booking, db, Gym
from time_utils import start_of_week, start_of_day, timeslot_index, parse
from utils import get_chosen_gym, is_admin
from app import fapp


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
            data["d"] = d = d - timedelta(days=7)
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
    [Input("location", "pathname")]
)
def path(path):
    navbar_items = [
        dbc.NavItem(html.A(html.Button("Gym", className="btn btn-primary"), href="/gym_admin")),
        # dbc.NavItem(),
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
        if path and path.endswith("gym_admin"):
            layout = create_gym_admin_layout()
        txt = f"{current_user.username} @ {get_chosen_gym().name}"
    return layout, navbar_items, txt


def create_heatmap(d, f, t):
    week_start_day = start_of_week(d)
    week_end_day = week_start_day + timedelta(days=8)

    all_bookings, my_bookings = create_weekly_booking_map(d)

    x = [(week_start_day.date() + timedelta(days=x)) for x in range(7)]
    start = datetime(1, 1, 1)
    y = [(start + timedelta(minutes=15 * k)).strftime("%H:%M") for k in range(24 * 4)]

    all_bookings[my_bookings > 0] = -3

    if f and week_start_day <= f <= week_end_day:
        start_idx = timeslot_index(f, week_start_day)
        all_bookings[start_idx] = -3.5
        if t:
            end_idx = timeslot_index(t, week_start_day)
            for _x in range(start_idx + 1, end_idx):
                all_bookings[_x] = -3.5

    if week_start_day < datetime.now() < week_end_day:
        all_bookings[:timeslot_index(datetime.now(), week_start_day) + 1] = -4.5

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
            if data["t"] is not None:
                data["t"] = str(date_picker_date) + "T" + data["t"].split("T")[-1]
            if data["f"] is not None:
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
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("New booking"),
                        dbc.CardBody([
                            html.Table([
                                html.Tr([
                                    html.Td([
                                        html.Span(html.I(className="fa fa-user-friends"))
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        html.Div(
                                            dbc.Input(
                                                value=1,
                                                id="nr_bookings",
                                                type="number",
                                                min=1,
                                                max=get_chosen_gym().max_number_per_booking if not is_admin() else get_chosen_gym().max_people
                                            )
                                        )
                                    ], style={"width": "50px"}),
                                ]),
                                html.Tr([
                                    html.Td([
                                        "Day"
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        dcc.DatePickerSingle(
                                            id="date-picker",
                                            date=datetime.now().date(),
                                            min_date_allowed=datetime.now().date(),
                                        )
                                    ], style={"width": "50px"}),
                                    html.Td(),
                                    html.Td([
                                        html.Div(dcc.DatePickerSingle(id="dummy"), style={"visibility": "hidden"})
                                    ])
                                ]),
                                html.Tr([
                                    html.Td([
                                        "Start"
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        dcc.Dropdown(
                                            id="from-drop-down",
                                            value=4 * 8,
                                            options=OPTIONS[:-1]
                                        )
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        "Stop"
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        dcc.Dropdown(
                                            id="to-drop-down",
                                            options=OPTIONS[:-1]
                                        )
                                    ], style={"width": "50px"})
                                ]),
                            ]),
                            dbc.Alert(id="msg", is_open=False, duration=5000, className="mt-2")
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
        ], width=3),
        dbc.Col([
            dbc.Container([
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
            ], fluid=True)
        ], width=7),
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

init_flask_admin()

if __name__ == '__main__':

    app.suppress_callback_exceptions = True
    app.run_server(debug=False, dev_tools_ui=False)
