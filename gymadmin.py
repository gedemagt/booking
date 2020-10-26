import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import State, ALL
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Trigger, Output
from dash_extensions.snippets import get_triggered

from app import app
from models import db, User, Zone
from utils import get_chosen_gym


@app.callback(
    [Output("save-gym-alert", "children"), Output("save-gym-alert", "color"), Output("save-gym-alert", "is_open")],
    [Trigger("save_gym_settings", "n_clicks")],
    [State("max_persons", "value"), State("max_booking_length", "value"), State("max_booking_per_user", "value"),
     State("max_time_per_user_per_day", "value"), State("max_number_per_booking", "value"),
     State("gym_admins", "value"), State(dict(type="zone-name", id=ALL), "value"), State(dict(type="zone-max-people", id=ALL), "value")]
)
def on_save_gym(max_persons, max_booking_length, max_booking_per_user,
                max_time_per_user_per_day, max_number_per_booking, admins, zone_name, zone_max_people):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    try:
        g = get_chosen_gym()

        g.max_people = max_persons
        g.max_booking_length = max_booking_length
        g.max_booking_per_user = max_booking_per_user
        g.max_time_per_user_per_day = max_time_per_user_per_day
        g.max_number_per_booking = max_number_per_booking

        for zone, name, capacity in zip(g.zones, zone_name, zone_max_people):
            zone.name = name
            zone.max_people = capacity

        get_chosen_gym().admins = [User.query.filter_by(id=x).first() for x in admins]
        db.session.add(g)
        db.session.commit()
        return "Success", "success", True
    except Exception as e:
        print(e)
        return str(e), "danger", True


def create_zones_list():
    return [
               html.Tr([
                   html.Td("Zone name"),
                   html.Td("Capacity"),
                   html.Td(dbc.Button(html.I(className="fa fa-plus"), id="add-zone", color="primary")),
               ])
           ] + \
           [
               html.Tr([
                    html.Td(
                        dbc.FormGroup([
                            dbc.Input(type="text", id=dict(type="zone-name", id=x.id), value=x.name),
                        ]),
                    ),
                    html.Td(
                        dbc.FormGroup([
                            dbc.Input(type="number", id=dict(type="zone-max-people", id=x.id), value=x.max_people, min=1),
                        ]),
                    ),
                    html.Td(
                        dbc.FormGroup([
                            dbc.Button(html.I(className="fa fa-trash"), id=dict(type="zone-delete", id=x.id),
                                       color="danger")
                        ])
                    ),
                ]) for x in get_chosen_gym().zones]


@app.callback(
    [Output("zone-edit", "children")],
    [Trigger("add-zone", "n_clicks"), Trigger(dict(type="zone-delete", id=ALL), "n_clicks")],
)
def on_new_zone():
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate
    if trig.id == "add-zone":
        try:
            g = get_chosen_gym()

            g.zones.append(Zone(name="New Zone", max_people=None))

            db.session.add(g)
            db.session.commit()

        except Exception as e:
            print(e)
    else:
        if len(get_chosen_gym().zones) == 1:
            raise PreventUpdate
        zone_id = trig.id["id"]
        db.session.delete(Zone.query.filter_by(id=zone_id).first())
        db.session.commit()

    return create_zones_list()


def create_gym_admin_layout():
    gym = get_chosen_gym()

    users = gym.users
    admins = gym.admins

    return dbc.Row([
        dbc.Col([], width=3),
        dbc.Col([
            dbc.Label("Gym settings", size="lg"),
            dbc.FormGroup([
                dbc.FormGroup(
                    [
                        dbc.Label("Max number of persons", html_for="max_persons"),
                        dbc.Input(type="number", id="max_persons", value=gym.max_people, min=1),
                        dbc.FormText(
                            "The capacity",
                            color="secondary",
                        ),
                    ],
                ),
                dbc.FormGroup(
                    [
                        dbc.Label("Max booking length", html_for="max_booking_length"),
                        dbc.Input(type="number", id="max_booking_length", value=gym.max_booking_length, min=1),
                        dbc.FormText(
                            "In number of timeslots (15 min)",
                            color="secondary",
                        ),
                    ],
                ),
                dbc.FormGroup(
                    [
                        dbc.Label("Max active bookings", html_for="max_booking_per_user"),
                        dbc.Input(type="number", id="max_booking_per_user", value=gym.max_booking_per_user, min=1),
                        dbc.FormText(
                            "The number of active booking a user can have",
                            color="secondary",
                        ),
                    ],
                ),
                dbc.FormGroup(
                    [
                        dbc.Label("Max timeslots per user per day", html_for="max_time_per_user_per_day"),
                        dbc.Input(type="number", id="max_time_per_user_per_day", value=gym.max_time_per_user_per_day,
                                  min=1),
                        dbc.FormText(
                            "The maximum number of timeslots (15 min) a user can have in one day",
                            color="secondary",
                        ),
                    ],
                ),
                dbc.FormGroup(
                    [
                        dbc.Label("Max persons per booking", html_for="max_number_per_booking"),
                        dbc.Input(type="number", id="max_number_per_booking", value=gym.max_number_per_booking, min=1),
                        dbc.FormText(
                            "How many persons can one person book for",
                            color="secondary",
                        ),
                    ],
                ),
                dbc.FormGroup(
                    [
                        dbc.Label("Gym admins", html_for="gym_admins"),
                        dcc.Dropdown(
                            id="gym_admins",
                            value=[x.id for x in admins],
                            options=[
                                {"label": x.username, "value": x.id} for x in users
                            ],
                            multi=True
                        ),
                    ],
                ),
            ]),
            dbc.Row([
                dbc.Col(dbc.Alert(id="save-gym-alert", is_open=False, duration=3000), width=8),
                dbc.Col(dbc.Row(dbc.Button("Save", id="save_gym_settings", color="primary"), justify="end"), width=4)
            ])
        ], width=3),
        dbc.Col([
            dbc.Label("Zone settings", size="lg"),
            html.Table(
                create_zones_list(),
                id="zone-edit",
            )
        ], width=3)
    ], className="p-3")
