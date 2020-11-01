import dash_core_components as dcc
import dash_bootstrap_components as dbc
from dash.dependencies import State
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered

from app import app
from models import Gym, User, db
from dash_extensions.enrich import Output, Input, Trigger


@app.callback(
    Output("gym-admin-dropdown", "value"),
    Input("user-admin-dropdown", "value")
)
def on_user(user):
    u = User.query.filter_by(id=user).first()

    if u:
        return [x.id for x in u.gyms]
    return None


@app.callback(
    Output("on-admin-change", "children"),
    Trigger("save-admin-change", "n_clicks"),
    [State("gym-admin-dropdown", "value"), State("user-admin-dropdown", "value")]
)
def on_admin_change(gyms, user):

    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate
    try:
        u = User.query.filter_by(id=user).first()
        gyms = [Gym.query.filter_by(id=_x).first() for _x in gyms] if gyms else []

        u.gyms = gyms
        db.session.add(u)
        db.session.commit()

        return "OK"
    except Exception as e:
        return str(e)


def create_admin_layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dcc.Dropdown(
                    id="user-admin-dropdown",
                    options=[{"label": x.username, "value": x.id} for x in User.query.all()]
                ),
                dcc.Dropdown(
                    id="gym-admin-dropdown",
                    options=[{"label": x.name, "value": x.id} for x in Gym.query.all()],
                    multi=True,
                ),
                dbc.Alert(id="on-admin-change"),
                dbc.Button("Save", id="save-admin-change")
            ], width=4)
        ], justify="around")
    ], fluid=True)
