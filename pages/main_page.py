from collections import defaultdict
from datetime import datetime, timedelta, date

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import ALL, ClientsideFunction
from dash_extensions.enrich import Output, Input, State, Trigger
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered
from flask_login import current_user

import numpy as np

import config
from app import app
from booking_logic import validate_booking, create_weekly_booking_map
from models import Booking, db
from time_utils import start_of_week, start_of_day, timeslot_index, parse, as_date
from utils import get_chosen_gym, is_admin, get_zone, zone_exists

BOOTSTRAP_BLUE = "#0275d8"
BOOTSTRAP_GREEN = "#5cb85c"
BOOTSTRAP_LIGHT_BLUE = "#5bc0de"
BOOTSTRAP_ORANGE = "#f0ad4e"
BOOTSTRAP_YELLOW = "#f0e24e"
BOOTSTRAP_RED = "#d9534f"


def parse_heatmap_click(data):
    return datetime.strptime(data["points"][0]["x"].split(" ")[0] + " " + data["points"][0]["y"], "%Y-%m-%d %H:%M")


def get_max_booking_length():
    return get_chosen_gym().max_booking_length if get_chosen_gym().max_booking_length is not None else 24*4


@app.callback(
    [Output("my-bookings", "children")],
    [Trigger("data-store", "data"), Trigger("bookings_store", "data")])
def redraw_all():
    return create_bookings()


@app.callback(
    [Output("data-store", "data")],
    [Input("selection_store", "data"), Input("view_store", "data"), Trigger("bookings_store", "data")])
def redraw_all(data, view_data):
    if len(current_user.gyms) == 0 or view_data["zone"] is None:
        raise PreventUpdate

    d = parse(data["d"])

    zone_id = view_data["zone"]
    _max = get_chosen_gym().get_max_people(zone_id)
    x, y, z, hover = create_heatmap(d, parse(data["f"]), parse(data["t"]), zone_id)
    return {"x": x, "y": y, "z": z, "max": _max, "close": config.CLOSE, "hover": hover}


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
    [State("selection_store", "data"), State("nr_bookings", "value"), State("view_store", "data")], group="ok"
)
def on_booking(data, nr_bookings, view_data):
    msg = ""
    msg_color = "warning"
    if date is not None and data["f"] is not None and data["t"] is not None:

        b_start = datetime.strptime(data["f"], "%Y-%m-%dT%H:%M:%S")
        b_end = datetime.strptime(data["t"], "%Y-%m-%dT%H:%M:%S")

        try:
            validate_booking(b_start, b_end, nr_bookings, view_data["zone"])
            db.session.add(Booking(start=b_start, end=b_end, user=current_user,
                                   zone=get_zone(view_data["zone"]), number=nr_bookings))
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

    return msg, msg_color, msg_color != "success", data


@app.callback(
    [Output("week", "children"), Output("next_week", "disabled"), Output("prev_week", "disabled")],
    [Input("selection_store", "data"), Input("view_store", "data"), Trigger("location", "pathname")]
)
def update_week(data, view_data):

    d = parse(data["d"])
    zone = get_zone(view_data["zone"])

    can_next_week = is_admin() or \
                    zone.gym.max_days_ahead is None or \
                    datetime.now() + timedelta(days=zone.gym.max_days_ahead) > d + timedelta(days=7)
    can_prev_week = datetime.now() < d

    return d.isocalendar()[1], not can_next_week, not can_prev_week


@app.callback(
    [Output("selection_store", "data")],
    [Trigger("prev_week", "n_clicks"), Trigger("next_week", "n_clicks")],
    [State("selection_store", "data"), State("view_store", "data")], group="ok"
)
def on_week(data, view_data):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    d = parse(data["d"])

    zone = get_zone(view_data["zone"])

    if trig.id == "next_week":
        if is_admin() or \
                zone.gym.max_days_ahead is None or \
                datetime.now() + timedelta(days=zone.gym.max_days_ahead) > d+timedelta(days=7):
            data["d"] = d + timedelta(days=7)
    if trig.id == "prev_week":
        if datetime.now() < d:
            data["d"] = d - timedelta(days=7)

    return data


def create_bookings():
    k = defaultdict(list)

    for x in current_user.bookings:
        if x.end >= datetime.now():
            k[x.start.date()].append(x)

    result = []
    for d in sorted(k.keys()):
        result.append(
            dbc.Row([
                dbc.Col(d.strftime("%d %b %Y"), width=7),
                dbc.Col("#", width=2)
            ], style={"background-color": "lightgrey"})
        )

        for b in k[d]:
            result.append(
                dbc.Row([
                    dbc.Col([
                        dbc.Row([
                            dbc.Col([
                                f'{b.start.strftime("%H:%M")} - {b.end.strftime("%H:%M")}',
                            ], width=12),
                            dbc.Col([
                                b.zone.name if len(get_chosen_gym().zones) > 1 else "",
                            ], width=12),
                        ])
                    ], width=7),
                    dbc.Col([
                        b.number,
                    ], width=2),
                    dbc.Col([
                        dbc.Button(html.I(className="fa fa-trash"), id=dict(type="delete-booking", bookingid=b.id),
                                   color="danger")
                    ], width=2)
                ], className="my-1")
            )
            result.append(html.Hr())

    return dbc.Container(dbc.Table(result, style={"width": "100%"}))


@app.callback(
    Output("popover", "is_open"),
    [Input("popover-target", "n_clicks")],
    [State("popover", "is_open")],
)
def toggle_popover(n, is_open):
    if n:
        return not is_open
    return is_open


def create_heatmap(d, f, t, zone_id):
    days = 7
    zone = get_zone(zone_id)
    week_start_day = start_of_week(d)
    week_end_day = week_start_day + timedelta(days=days)

    all_bookings, my_bookings = create_weekly_booking_map(d, zone_id, days)
    hover = all_bookings.copy()

    x = [(week_start_day.date() + timedelta(days=x)) for x in range(days)]
    start = datetime(1, 1, 1)
    y = list(reversed([(start + timedelta(minutes=15 * k)).strftime("%H:%M") for k in range(24 * 4)]))

    all_bookings[my_bookings > 0] = -3

    if f and week_start_day <= f < week_end_day:

        start_idx = timeslot_index(f, week_start_day)

        all_bookings[start_idx] = -3.5
        if t:
            end_idx = timeslot_index(t, week_start_day)
            for _x in range(start_idx + 1, end_idx):
                all_bookings[_x] = -3.5

    if week_start_day < datetime.now():
        all_bookings[:timeslot_index(datetime.now(), week_start_day) + 1] = -4.5

    if not is_admin() and zone.gym.max_days_ahead is not None and \
            start_of_day(datetime.now()) + timedelta(days=zone.gym.max_days_ahead) < week_end_day:
        latest = timeslot_index(start_of_day(datetime.now()) + timedelta(days=zone.gym.max_days_ahead + 1), week_start_day)
        all_bookings[max(latest, 0):] = -4.5

    z = np.flipud(np.reshape(all_bookings, (days, 24 * 4)).transpose())
    hover = np.flipud(np.reshape(hover, (days, 24 * 4)).transpose())

    return x, y, z, hover


OPTIONS = [{'label': (datetime(1, 1, 1) + timedelta(minutes=15 * x)).strftime("%H:%M"), 'value': x} for x in
           range(24 * 4 + 1)]


@app.callback(
    [Output("msg2", "children"), Output("msg2", "color"), Output("msg2", "is_open"), Output("book", "disabled")],
    [Input("selection_store", "data"), Trigger("nr_bookings", "value")],
    [State("nr_bookings", "value"), State("view_store", "data")]
)
def val_booking(data, nr, view_data):

    if data["f"] is not None and data["t"] is not None:
        try:
            validate_booking(parse(data["f"]), parse(data["t"]), nr, view_data["zone"])
        except AssertionError as e:
            return str(e), "danger", True, True
    return "Empty", "success", False, False


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

            max_dt = timedelta(minutes=15 * get_max_booking_length())
            if data["t"] - data["f"] > max_dt:
                data["t"] = data["f"] + max_dt

        data["source"] = "graph"
    else:
        picked_date = datetime.strptime(date_picker_date, "%Y-%m-%d")
        d = start_of_week(picked_date)

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
        data["d"] = d
    return data


@app.callback(
    [Output("from-drop-down", "options"), Output("from-drop-down", "value"), Output("to-drop-down", "options"),
     Output("to-drop-down", "value"), Output("date-picker", "date")],
    [Input("selection_store", "data")],
    [State("from-drop-down", "value"), State("to-drop-down", "value"),
     State("date-picker", "date")]
)
def update_inputs(data, prev_from, prev_to, prev_date):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    from_value = None
    to_value = None

    day = prev_date

    if data.get("source", "") == "graph":
        day = start_of_day(datetime.now())
        if data["f"] is not None:
            d = parse(data["f"])
            day = start_of_day(d)
            from_value = timeslot_index(d)
        if data["t"] is not None:
            d = parse(data["t"])
            to_value = timeslot_index(d)
        day = day.date()
    elif data.get("source", "") == "input":

        from_value = prev_from if data["f"] is not None else None
        to_value = prev_to if data["t"] is not None else None

    from_min_index = timeslot_index(datetime.now()) + 1 if as_date(day) == datetime.now().date() else 0
    from_max_index = len(OPTIONS) - 1

    if from_value is not None:
        to_min_index = from_value + 1
        to_max_index = from_value + 1 + get_max_booking_length() if not is_admin() else len(OPTIONS) - 1
    else:
        to_min_index = from_min_index + 1
        to_max_index = len(OPTIONS) - 1

    if from_value is not None:
        from_value = from_value

    if to_value is not None:
        to_value = to_value

    return OPTIONS[from_min_index:from_max_index], from_value, OPTIONS[to_min_index:to_max_index], to_value, day


@app.callback(
    [Output("prev-zone", "disabled"), Output("next-zone", "disabled"),
     Output("mobile-zone", "children"), Output("zone-picker", "value")],
    [Input("view_store", "data")]
)
def update_zone(data):
    zone = get_zone(data["zone"])
    if len(zone.name) > 10:
        name = zone.name[:10] + "..."
    else:
        name = zone.name
    return zone.gym.zones[0].id == zone.id, zone.gym.zones[-1].id == zone.id, name, zone.id


@app.callback(
    Output("view_store", "data"),
    [Trigger("show-all", "n_clicks"), Trigger("show-am", "n_clicks"),
     Trigger("show-pm", "n_clicks"), Trigger("show-peak", "n_clicks"),
     Trigger("show-all-2", "n_clicks"), Trigger("show-am-2", "n_clicks"),
     Trigger("show-pm-2", "n_clicks"), Trigger("show-peak-2", "n_clicks"),
     Trigger("zone-picker", "value"), Trigger("next-zone", "n_clicks"), Trigger("prev-zone", "n_clicks"), Trigger("show-text", "n_clicks"), Trigger("show-text-2", "n_clicks")],
    [State("view_store", "data")]
)
def show_selection(data):
    trig = get_triggered()

    zone = get_zone(data["zone"])
    # Find current zone index:
    current_idx = 0
    for idx, zone in enumerate(zone.gym.zones):
        if zone.id == data["zone"]:
            current_idx = idx

    if trig.id == "zone-picker":
        data["zone"] = trig.value
    elif trig.id == "next-zone" and current_idx < len(zone.gym.zones) - 1:
        data["zone"] = zone.gym.zones[current_idx + 1].id
    elif trig.id == "prev-zone" and current_idx > 0:
        data["zone"] = zone.gym.zones[current_idx - 1].id
    else:
        if trig.n_clicks is None:
            raise PreventUpdate

        if trig.id.startswith("show-all"):
            data["show"] = "all"
        elif trig.id.startswith("show-am"):
            data["show"] = "am"
        elif trig.id.startswith("show-pm"):
            data["show"] = "pm"
        elif trig.id.startswith("show-peak"):
            data["show"] = "peak"
        elif trig.id.startswith("show-text"):
            data["show_text"] = not data.get("show_text", False)

    return data


app.clientside_callback(
    """
    function placeholder(date) {
        if (document.getElementById("date")) {
            document.getElementById("date").setAttribute("readonly", "readonly");
        }
        return [screen.width];
    }
    """,
    [Output("dummy", "children")],
    [Input("date-picker", "date")]
)

app.clientside_callback(
    ClientsideFunction(
        namespace='clientside',
        function_name='set_fig'
    ),
    [Output("main-graph", "figure")],
    [Input("data-store", "data")],
    [State("view_store", "data")]
)


@app.callback(
    Output("date-picker", "with_full_screen_portal"),
    Input("dummy", "children")
)
def on_screen_width(s):
    screen_width = int(s)
    return screen_width < 768


@app.callback(
    Output("nr_bookings", "options"),
    Input("view_store", "data")
)
def nr_bookings_options(view_data):
    zone = get_zone(view_data["zone"])

    if is_admin():
        max_nr = zone.max_people if zone.max_people is not None else zone.gym.max_people
    else:
        if zone.gym.max_number_per_booking is not None:
            max_nr = zone.gym.max_number_per_booking
        else:
            max_nr = zone.max_people if zone.max_people is not None else zone.gym.max_people

    return [{"value": x, "label": x} for x in range(1, max_nr+1)]


@app.callback(
    [Output("progress-spinner", "hidden")],
    [Trigger("prev_week", "n_clicks"), Trigger("next_week", "n_clicks"),
     Trigger("prev-zone", "n_clicks"), Trigger("next-zone", "n_clicks"),
     Trigger("show-text", "n_clicks"), Trigger("show-text-2", "n_clicks"), Trigger("main-graph", "figure")],
    [State("view_store", "data")]
)
def do(view_data):
    trig = get_triggered()
    if trig.id == "main-graph" and view_data["zone"] is not None:
        return True
    else:
        return False


def create_zone_picker(id, gym):
    return html.Div(
        dbc.Row([
            dbc.Col([
                html.Span("Zone")
            ], width=3, style={"margin": "auto"}),
            dbc.Col([
                dcc.Dropdown(
                    id=id,
                    options=[{"label": x.name, "value": x.id} for x in gym.zones],
                    value=gym.zones[0].id,
                    clearable=False,
                    searchable=False,
                    style={"width": "100%"}
                )
            ], width=9)
        ], justify="between", className="my-1"),
        hidden=len(gym.zones) == 1
    )


def create_main_layout(gym):
    return dbc.Row([
        html.Div(id="dummy2", hidden=True),
        html.Div(id="dummy", hidden=True),
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    html.H4(f"Welcome {current_user.username}", className="my-3"),
                    dbc.Card([
                        dbc.CardHeader("New booking"),
                        dbc.CardBody([
                            create_zone_picker("zone-picker", gym),
                            html.Div([
                                dbc.Row([
                                    dbc.Col([
                                        html.Span(html.I(className="fa fa-user-friends"))
                                    ], width=3, style={"margin": "auto"}),
                                    dbc.Col([
                                        dcc.Dropdown(
                                            id="nr_bookings",
                                            value=1,
                                            options=[{"value": 1, "label": 1}],
                                            clearable=False
                                        )
                                    ], width=9)
                                ], justify="between", className="my-1"),
                            ], hidden=gym.max_number_per_booking == 1 and not is_admin()),
                            dbc.Row([
                                dbc.Col([
                                    html.Span("Day")
                                ], width=3, style={"margin": "auto"}),
                                dbc.Col([
                                    html.Div([
                                        dcc.DatePickerSingle(
                                            id="date-picker",
                                            date=datetime.now().date(),
                                            min_date_allowed=datetime.now().date(),
                                            max_date_allowed=datetime.now().date() + timedelta(days=gym.max_days_ahead) if not is_admin() and gym.max_days_ahead else None,
                                            display_format="DD-MM-YYYY",
                                            clearable=False,
                                            first_day_of_week=1
                                        )
                                    ])
                                ], width=9)
                            ], justify="between", className="my-1"),
                            dbc.Row([
                                dbc.Col([
                                    html.Span("Time")
                                ], width=3, style={"margin": "auto"}),
                                dbc.Col([
                                    dbc.Row([
                                        dbc.Col([
                                            dcc.Dropdown(
                                                id="from-drop-down",
                                                value=4 * 8,
                                                options=OPTIONS[:-1],
                                                searchable=False,
                                            )
                                        ], width=12, sm=5),
                                        dbc.Col([
                                            html.Div("-", style={"text-align": "center", "margin": "auto"})
                                        ], width=0, sm=2),
                                        dbc.Col([
                                            dcc.Dropdown(
                                                id="to-drop-down",
                                                options=OPTIONS[:-1],
                                                searchable=False,
                                            )
                                        ], width=12, sm=5)
                                    ])
                                ], width=9)
                            ], justify="between", className="my-1"),
                            dbc.Alert(id="msg", is_open=False, duration=5000, className="mt-3"),
                            dbc.Alert("Empty", id="msg2", is_open=False, className="mt-3 mb-0"),
                        ]),
                        dbc.CardFooter([
                            dbc.Row([dbc.Button("Book", id="book", color="primary")], justify="end")
                        ])
                    ])
                ], width=12)
            ]),
            dbc.Card([
                dbc.CardHeader("My bookings"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Div(id="my-bookings")
                        ])
                    ])
                ])
            ], className="my-3")
        ], width=12, lg=3),
        dbc.Col([
            dbc.Container([
                html.Div([dbc.Row([
                    dbc.Col([
                        dbc.Row([
                            dbc.Badge("Free slots", color="white", className="mx-1 mb-1"),
                            dbc.Badge(f"Booked", color="success", className="mx-1 mb-1"),
                        ]),
                        dbc.Row([
                            dbc.Badge("Full", color="danger", className="mx-1 mb-1"),
                            dbc.Badge(f"1", color="warning", className="mx-1 mb-1"),
                            dbc.Badge(f"2-3", className="mx-1 mb-1",
                                      style={"background-color": BOOTSTRAP_YELLOW, "color": "black"}),
                            dbc.Badge(f"4+", color="primary", className="mx-1 mb-1"),

                        ])

                    ], width=7),
                    dbc.Col([
                        dbc.Row([
                            dbc.Button(html.I(className="fa fa-users"), id="show-text-2",
                                       className="mx-1", color="primary"),
                            dbc.DropdownMenu([
                                dbc.DropdownMenuItem("24h", id="show-all-2"),
                                dbc.DropdownMenuItem("AM", id="show-am-2"),
                                dbc.DropdownMenuItem("PM", id="show-pm-2"),
                                dbc.DropdownMenuItem("Peak", id="show-peak-2")
                            ], label="\u231A", color="primary")
                        ], justify="end")
                    ], width=5, style={"text-align": "right"})
                ], justify="between", className="my-3")], className=" d-block d-md-none"),

                dbc.Row([
                    dbc.Col([
                        dbc.Row([dbc.Badge("Free slots", color="white", className="mx-1 mb-1")]),
                        dbc.Row([
                            dbc.Badge("Full", color="danger", className="mx-1 mb-1"),
                            dbc.Badge(f"1", color="warning", className="mx-1 mb-1"),
                            dbc.Badge(f"2-3", className="mx-1 mb-1",
                                      style={"background-color": BOOTSTRAP_YELLOW, "color": "black"}),
                            dbc.Badge(f"4+", color="primary", className="mx-1 mb-1"),
                            dbc.Badge(f"Booked", color="success", className="mx-1 mb-1")
                        ])
                    ], style={"margin-top": "auto"}, width=3, className="d-none d-md-block"),
                    dbc.Col([
                        html.Div([
                            dbc.Button("<", id="prev_week", color="primary", disabled=True, size="sm"),
                            html.Span([
                                html.Span([
                                    html.Span("Week", className="ml-3 mr-1"),
                                    html.Span(datetime.now().isocalendar()[1], id="week", className="mr-3 ml-1"),

                                ], id="week-text", style={"position": "relative"}),

                            ], style={"width": "100%"}),
                            dbc.Button(">", id="next_week", color="primary", size="sm")
                        ], style={"text-align": "center"})
                    ], width=12, md=6),
                    dbc.Col([
                        dbc.Row([
                            dbc.Button(html.I(className="fa fa-users"), id="show-text",
                                       className="mx-1", color="primary"),
                            dbc.DropdownMenu([
                                dbc.DropdownMenuItem("24h", id="show-all"),
                                dbc.DropdownMenuItem("AM", id="show-am"),
                                dbc.DropdownMenuItem("PM", id="show-pm"),
                                dbc.DropdownMenuItem("Peak", id="show-peak")
                            ], label="\u231A", color="primary")
                        ], justify="end")
                    ], width=3, style={"text-align": "right"}, className="d-none d-md-block")
                ], justify="between", className="my-3"),
                html.Div([
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                dbc.Button("<", id="prev-zone", color="primary", size="sm"),
                                html.Span([
                                    html.Span(id="mobile-zone", className="mx-3"),
                                ]),
                                dbc.Button(">", id="next-zone", color="primary", size="sm")
                            ], style={"text-align": "center"})
                        ], width=12)
                    ], justify="around", className="d-block d-md-none")
                ], hidden=len(gym.zones) < 2),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            dcc.Graph(
                                id="main-graph",
                                style={"height": "70vh", "width": "100%"}),
                            html.Span([
                                dbc.Spinner(color="primary", size="lg")
                            ], id="progress-spinner",
                                style={"position": "absolute",
                                       "width": "100%",
                                       "left": "0", "top": "0"})
                        ], style={"position":"relative"}),
                    ], className="px-0", width=12),
                ], justify="between", className="px-0"),
            ], fluid=True, className="px-0")
        ], width=12, lg=7),
    ], className="p-3")
