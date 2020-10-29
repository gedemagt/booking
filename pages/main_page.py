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
from app import app
from booking_logic import validate_booking, create_weekly_booking_map
from models import Booking, db, Gym
from time_utils import start_of_week, start_of_day, timeslot_index, parse, as_date
from utils import get_chosen_gym, is_admin


def parse_heatmap_click(data):
    return datetime.strptime(data["points"][0]["x"].split(" ")[0] + " " + data["points"][0]["y"], "%Y-%m-%d %H:%M")


@app.callback(
    [Output("my-bookings", "children"), Output("main-graph", "figure")],
    [Input("bookings_store", "data"), Input("selection_store", "data"), Input("view_store", "data")], group="redraw")
def redraw_all(data1, data, view_data):
    d = parse(data["d"])
    return create_bookings(), create_heatmap(d, parse(data["f"]), parse(data["t"]), view_data["show"], view_data["zone"])


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
            validate_booking(b_start, b_end, int(nr_bookings), view_data["zone"])
            zone = next(x for x in get_chosen_gym().zones if x.id == view_data["zone"])
            db.session.add(Booking(start=b_start, end=b_end, user=current_user,
                                   zone=zone, number=int(nr_bookings)))
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

    return msg, msg_color, False, data


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


def create_bookings():
    k = defaultdict(list)

    for x in current_user.bookings:
        if x.end >= datetime.now():
            k[x.start.date()].append(x)

    result = []
    for d in sorted(k.keys()):
        result.append(
            html.Tr([
                html.Td(d.strftime("%d %b %Y"), style={"background-color": "lightgrey"}, colSpan=4),
                html.Td("#", style={"background-color": "lightgrey"}, colSpan=2),
            ])
        )
        for b in k[d]:
            result.append(
                html.Tr([
                    html.Td(b.start.strftime("%H:%M"), style={"text-align": "left"}),
                    html.Td("-", style={"text-align": "left"}),
                    html.Td(b.end.strftime("%H:%M"), style={"text-align": "left"}),
                    html.Td(b.zone.name, style={"text-align": "left"}),
                    html.Td(b.number, style={"text-align": "left"}),
                    html.Td(dbc.Button(html.I(className="fa fa-trash"), id=dict(type="delete-booking", bookingid=b.id), color="danger"))
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
    [Output("location", "pathname"), Output("gym-err", "children"), Output("gym-err", "is_open")],
    [Input("add_gym", "n_clicks")],
    [State("gym_code", "value")]
)
def on_new_gym(n, gym_code):
    if gym_code is not None:
        g = db.session.query(Gym).filter_by(code=gym_code).first()
        if g:
            current_user.gyms.append(g)
            db.session.commit()
            return "/", "", False

    return "/", "Gym not found", n is not None


def create_heatmap(d, f, t, yrange, zone):
    week_start_day = start_of_week(d)
    week_end_day = week_start_day + timedelta(days=8)

    all_bookings, my_bookings = create_weekly_booking_map(d, zone)
    hover = all_bookings.copy()

    x = [(week_start_day.date() + timedelta(days=x)) for x in range(7)]
    start = datetime(1, 1, 1)
    y = list(reversed([(start + timedelta(minutes=15 * k)).strftime("%H:%M") for k in range(24 * 4)]))

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

    z = np.flipud(np.reshape(all_bookings, (7, 24 * 4)).transpose())
    hover = np.flipud(np.reshape(hover, (7, 24 * 4)).transpose())

    _max = get_chosen_gym().get_max_people(zone)
    _close = _max - config.CLOSE
    l = _max + 5

    if yrange == "am":
        y_range = [12*4, 24*4]
    elif yrange == "pm":
        y_range = [0*4, 12*4]
    else:
        y_range = [0, 24*4]

    fig = go.Figure(
        layout=go.Layout(
            margin=dict(t=0, r=0, l=0, b=0),
            xaxis=dict(fixedrange=True, mirror="allticks", side="top"),
            yaxis=dict(fixedrange=True, range=y_range),

        ),
        data=go.Heatmap(
            name="",
            z=z,
            x=x,
            y=y,
            text=hover,
            hovertemplate="%{y}: %{text}",
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
                ((_close + 5) / l, "orange"), (0.99, "orange"),
                (0.99, "red"), (1.0, "red")
            ]
        )
    )

    fig.update_layout(
        yaxis=dict(
            tickmode='linear',
            tick0=7,
            dtick=4
        )
    )

    fig.update_layout(
        xaxis_tickformat='%a %d %b'
    )

    return fig


OPTIONS = [{'label': (datetime(1, 1, 1) + timedelta(minutes=15 * x)).strftime("%H:%M"), 'value': x} for x in
           range(24 * 4 + 1)]


@app.callback(
    [Output("msg2", "children"), Output("msg2", "color"),
     Output("msg2-container", "style"), Output("book", "disabled")],
    [Input("selection_store", "data")],
    [State("nr_bookings", "value"), State("view_store", "data")]
)
def val_booking(data, nr, view_data):
    style = {"visibility": "hidden"}
    if data["f"] is not None and data["t"] is not None:
        try:
            validate_booking(parse(data["f"]), parse(data["t"]), int(nr), view_data["zone"])
        except AssertionError as e:
            style = {"visibility": "visible"}
            return str(e), "danger", style, True
    return "Empty", "success", style, False


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
    [Output("from-drop-down", "options"), Output("from-drop-down", "value"), Output("to-drop-down", "options"),
     Output("to-drop-down", "value"), Output("date-picker", "date")],
    [Input("selection_store", "data")],
    [State("from-drop-down", "options"), State("from-drop-down", "value"), State("to-drop-down", "options"),
     State("to-drop-down", "value"), State("date-picker", "date")]
)
def update_inputs(data, prev_from_options, prev_from, prev_to_options, prev_to, prev_date):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    from_value = None
    to_value = None
    options = prev_to_options

    date = prev_date

    if data.get("source", "") == "graph":
        date = start_of_day(datetime.now())
        if data["f"] is not None:
            d = parse(data["f"])
            date = start_of_day(d)
            from_value = int((d - start_of_day(d)).total_seconds() / 60 / 15)
        if data["t"] is not None:
            d = parse(data["t"])
            to_value = int((d - start_of_day(d)).total_seconds() / 60 / 15)
        date = date.date()
        options = OPTIONS[from_value + 1:] if from_value else OPTIONS[1:]
    elif data.get("source", "") == "input":
        from_value = prev_from if data["f"] is not None else None
        options = prev_to_options if data["f"] is None else OPTIONS[int((parse(data["f"]) - start_of_day(parse(data["f"]))).total_seconds() / 60 / 15) + 1:]
        to_value = prev_to if data["t"] is not None else None

    if as_date(date) == datetime.now().date():
        prev_from_options = OPTIONS[timeslot_index(datetime.now())+1:]
        if from_value is None:
            options = OPTIONS[timeslot_index(datetime.now())+2:]
    else:
        prev_from_options = OPTIONS

    return prev_from_options, from_value, options, to_value, date


@app.callback(
    Output("view_store", "data"),
    [Trigger("show-all", "n_clicks"), Trigger("show-am", "n_clicks"), Trigger("show-pm", "n_clicks"),
     Trigger("zone-picker", "value")],
    [State("view_store", "data")]
)
def show_selection(data):
    trig = get_triggered()

    if trig.id == "zone-picker":
        data["zone"] = trig.value
    else:
        if trig.n_clicks is None:
            raise PreventUpdate

        if trig.id == "show-all":
            data["show"] = "all"
        elif trig.id == "show-am":
            data["show"] = "am"
        elif trig.id == "show-pm":
            data["show"] = "pm"

    return data


def create_main_layout():
    return dbc.Row([
        dbc.Col([
            dbc.Row([
                dbc.Col([
                    html.H4(f"Welcome {current_user.username}", className="my-3"),
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
                                            display_format="DD-MM-YYYY"
                                        )
                                    ], style={"width": "50px"}),
                                    html.Td(),
                                    html.Td([
                                        html.Div(dcc.DatePickerSingle(id="dummy"), style={"visibility": "hidden"})
                                    ])
                                ]),
                                html.Tr([
                                    html.Td([
                                        "Time"
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        dcc.Dropdown(
                                            id="from-drop-down",
                                            value=4 * 8,
                                            options=OPTIONS[:-1]
                                        )
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        html.Div("-", className="text-center")
                                    ], style={"width": "50px"}),
                                    html.Td([
                                        dcc.Dropdown(
                                            id="to-drop-down",
                                            options=OPTIONS[:-1]
                                        )
                                    ], style={"width": "50px"})
                                ]),
                            ]),
                            dbc.Alert(id="msg", is_open=False, duration=5000, className="mt-3"),
                            html.Div(dbc.Alert("Empty", id="msg2", is_open=True, className="mt-3 mb-0"), id="msg2-container", style={"visibility": "hidden"})
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
                dbc.Row([
                    dbc.Col([
                        dbc.Row([
                            dcc.Dropdown(
                                id="zone-picker",
                                options=[{"label": x.name, "value": x.id} for x in get_chosen_gym().zones],
                                value=get_chosen_gym().zones[0].id,
                                clearable=False,
                                style={"width": "100%"}
                            )
                        ], justify="start")
                    ], width=2),
                    dbc.Col(width=1),
                    dbc.Col([
                        html.Div([
                            dbc.Button("<", id="prev_week", color="primary"),
                            html.Span([
                                html.Span("Week", className="ml-3 mr-1"),
                                html.Span(datetime.now().isocalendar()[1], id="week", className="mr-3 ml-1"),
                            ]),
                            dbc.Button(">", id="next_week", color="primary")
                        ], style={"text-align": "center"})
                    ], width=6),
                    dbc.Col([
                        dbc.Row(
                            dbc.ButtonGroup(
                                [
                                    dbc.Button("24H", id="show-all", color="secondary"),
                                    dbc.Button("AM", id="show-am", color="secondary"),
                                    dbc.Button("PM", id="show-pm", color="secondary")
                                ]
                            ),
                            justify="end"
                        )
                    ], width=3)
                ], justify="between", className="my-3 mr-2"),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            dcc.Graph(
                                figure=create_heatmap(datetime.now(), None, None, "pm", get_chosen_gym().zones[0].id),
                                id="main-graph",
                                style={"height": "70vh", "width": "100%"})
                        ], className="my-3"),
                    ], width=12),
                ], justify="between"),
            ], fluid=True)
        ], width=12, lg=7),
    ], className="p-3")



