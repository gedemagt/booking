
import dash_bootstrap_components as dbc
import dash_html_components as html
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered
from flask_login import current_user

from app import app
from dash_extensions.enrich import Output, Input, State

from models import db, Gym


@app.callback(
    [Output("location", "pathname")],
    [Input("gym-err", "children")]
)
def on_new_gym(status):
    if status == "OK":
        return "/"
    raise PreventUpdate


@app.callback(
    [Output("gym-err", "children"), Output("gym-err", "is_open")],
    [Input("add_gym", "n_clicks")],
    [State("gym_code", "value")]
)
def on_new_gym(n, gym_code):
    trig = get_triggered()
    if trig.id is None:
        raise PreventUpdate

    if gym_code is not None:
        g = db.session.query(Gym).filter_by(code=gym_code).first()
        if g:
            current_user.gyms.append(g)
            db.session.commit()
            return "OK", False

    return "Gym not found", n is not None


def create_enter_gym_layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3("Please enter gym code", className="my-3"),
                dbc.InputGroup([dbc.Input(id="gym_code")], className="mb-2"),
                dbc.Button("OK", id="add_gym", color="primary", className="mb-2"),
                dbc.Alert(id="gym-err", is_open=False, duration=3000, color="danger")
            ], width=4)
        ], justify="around"),
        html.Div(id="hidden_div_for_redirect_callback")
    ], fluid=True)
