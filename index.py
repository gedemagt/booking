from datetime import datetime, timedelta

from flask_login import current_user

from app import app, fapp
from pages.admin_page import create_admin_layout
from pages.enter_gym_page import create_enter_gym_layout
from pages.gym_page import create_gym_admin_layout
from pages.main_page import create_main_layout
from time_utils import start_of_week

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash_extensions.enrich import Output, Input

from utils import is_admin, get_chosen_gym


app.layout = html.Div([
    html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
    dcc.Store(id="selection_store", data={"f": None, "t": None, "d": start_of_week(),
                                          "source": None}),
    dcc.Store(id="bookings_store", data={}),
    dcc.Store(id="data-store", data={}),
    dcc.Store(id="view_store", data={"show": "peak", "zone": None}, storage_type='local'),
    dcc.Location(id="location"),
    html.Div(id="redirect"),
    dbc.NavbarSimple(
        children=[],
        brand="Booking",
        brand_href="/",
        color="primary",
        dark=True,
        id="navbar",
        fluid=True
    ),
    dbc.Modal(
        [
            html.Div(id="b-edit-id", hidden=True),
            html.Div(id="b-edit-type", hidden=True),
            dbc.ModalHeader("Booking note"),
            dbc.ModalBody(dbc.Textarea(id="booking-note-input")),
            dbc.ModalFooter(
                dbc.Button("Save", id="ok-edit-booking", color="primary", className="ml-auto")
            ),
        ],
        id="edit-booking-modal",
    ),
    dbc.Container(html.Div(id="layout"), fluid=True)
])


@app.callback(
    [Output("layout", "children"), Output("navbar", "children"), Output("navbar", "brand")],
    [Input("location", "pathname")], group="view"
)
def path(p):

    navbar_items = [
        dbc.NavItem(dcc.LogoutButton("Logout", logout_url="/user/sign-out", className="btn btn-primary"))
    ]

    if current_user.email_confirmed_at is None:
        return dcc.Location("some_id", "/user/resend-email-confirmation"), navbar_items, ""

    if current_user.role == "ADMIN":
        navbar_items.insert(0, dbc.NavItem(dcc.Link(html.I(className="fa fa-cog"), className="btn btn-primary", href="/superadmin")))

    if len(current_user.gyms) == 0:
        layout = create_enter_gym_layout()
        txt = f"{current_user.username}"
    else:
        if is_admin():
            navbar_items.insert(0, dbc.NavItem(dcc.Link(html.I(className="fa fa-cogs"), className="btn btn-primary", href="/gym_admin")))

        if p and p.endswith("gym_admin") and is_admin():
            layout = create_gym_admin_layout()
        elif p and p.endswith("superadmin") and current_user.role == "ADMIN":
            layout = create_admin_layout()
        else:
            # max_days_ahead = get_chosen_gym().max_days_ahead
            # if datetime.now() < datetime(2021, 1, 3) - timedelta(days=max_days_ahead + 1) if max_days_ahead else :
            #     layout = dbc.Container(dbc.Row(html.Img(src="assets/3u624n.jpg", style={"max-width": "100%"}), justify="around", className="pt-3"))
            # else:
            layout = create_main_layout(get_chosen_gym())

        txt = f"{get_chosen_gym().name}"
    return layout, navbar_items, txt


if __name__ == '__main__':

    app.run_server(host="0.0.0.0", debug=True, dev_tools_ui=True)
