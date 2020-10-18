import os
from datetime import datetime, timedelta, date

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, ALL, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions.snippets import get_triggered
from flask import Flask
from flask_login import current_user
from flask_sqlalchemy import SQLAlchemy
from flask_user import UserManager, UserMixin, login_required

import numpy as np

import config
from custom import CustomUserManager
from flask_config import ConfigClass

fapp = Flask(__name__)
fapp.config.from_object(__name__+'.ConfigClass')
app = dash.Dash(server=fapp, external_stylesheets=[dbc.themes.BOOTSTRAP])

db = SQLAlchemy(fapp)




class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column('is_active', db.Boolean(), nullable=False, server_default='1')

    username = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)

    email = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)
    email_confirmed_at = db.Column(db.DateTime())
    password = db.Column(db.String(255), nullable=False, server_default='')

    role = db.Column(db.String(100, collation='NOCASE'), nullable=False, server_default='')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    user = db.Column(db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'))


user_manager = CustomUserManager(fapp, db, UserClass=User)
db.create_all()


def create_from_to(f, t):
    new_booking = np.zeros(24 * 4)
    for x in range(f, t + 1):
        new_booking[x] += 1
    return new_booking


def get_bookings(d: date):
    all_bookings = [0] * 24 * 4
    my_bookings = [0] * len(all_bookings)
    for b in Booking.query.filter(Booking.start >= d).filter(Booking.end <= d + timedelta(days=1)).all():
        start = (b.start - datetime(d.year, d.month, d.day)).seconds / 60 / 15
        end = (b.end - datetime(d.year, d.month, d.day)).seconds / 60 / 15
        for x in range(int(start), int(end)):
            all_bookings[x] += 1
        if current_user and b.user == current_user.id:
            for x in range(int(start), int(end)):
                my_bookings[x] += 1
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
        return current[row * config.COLUMNS * 4 + column] < config.MAX

    def is_close(row, column):
        return config.CLOSE <= current[row * config.COLUMNS * 4 + column] < config.MAX

    def is_yours(row, column):
        return my_bookings[row * config.COLUMNS * 4 + column] > 0

    def get_color(row, column):
        if selected(row, column):
            return "grey"
        elif is_close(row, column):
            return "orange"
        elif is_yours(row, column):
            return "green"
        elif is_available(row, column):
            return "blue"
        else:
            return "red"

    rows = []
    dt = datetime(1, 1, 1)
    for x in range(config.ROWS):
        rows.append(
            html.Tr([
                html.Td(
                    html.Button(
                        str(config.MAX - current[x * config.COLUMNS * 4 + k]) if config.MAX > current[x * config.COLUMNS * 4 + k] >= config.CLOSE else "",
                        style={"width": "35px", "height": "35px", "border": "none",
                               "background-color": get_color(x, k), "color": "white", "font-weight": "bold"},
                        id=dict(type="time-tile", column=k, row=x)
                    ),
                    style={"text-align": "right"}
                )
                for k in range(config.COLUMNS * 4)
            ])
        )
        rows.append(
            html.Tr([
                html.Td(
                    (dt + timedelta(minutes=(x * config.COLUMNS * 4 + k) * 15)).strftime("%H:%M")
                    if (x * config.COLUMNS * 4 + k) % 4 == 0 else ""
                )
                for k in range(6 * 4)
            ])
        )
    return rows


# @app.callback(
#     [Output("bookings_store", "data")],
#     [Input("book", "n_clicks"),
#      Input(dict(type="delete-booking", bookingid=ALL), "n_clicks")],
#     [State("datepicker", "date"), State()]
# )
# def erik(book_n_clicks, delete_n_clicks, selected_date):
#     trig = get_triggered()
#     if trig.id is None:
#         raise PreventUpdate
#
#     selected_date = datetime.strptime(selected_date, "%Y-%m-%d")
#
#     bookings, my_bookings = get_bookings(selected_date)
#
#     if trig.id == "book":
#         if date is not None and data["f"] is not None and data["t"] is not None:
#
#             b_start = d + timedelta(minutes=15 * data["f"])
#             b_end = d + timedelta(minutes=15 * (data["t"] + 1))
#
#             new_booking = create_from_to(data["f"], data["t"])
#
#             if np.any((bookings + new_booking) > config.MAX):
#                 msg = "Booking interval is overlapping with a full time slot"
#             elif np.any((new_booking + my_bookings) > 1):
#                 msg = "Booking interval is overlapping with a previous booking"
#             else:
#                 db.session.add(Booking(start=b_start, end=b_end, user=current_user.id))
#                 db.session.commit()
#                 msg = "Booking successfully created"
#                 msg_color = "success"
#             data = {"f": None, "t": None}
#         else:
#             msg = "Data is wierd..."

@app.callback(
    [Output("main", "children"), Output("selection_store", "data"),
     Output("msg", "children"), Output("msg", "color"), Output("msg", "is_open"), Output("my-bookings", "children")],
    [Input("clear", "n_clicks"), Input("book", "n_clicks"),
     Input(dict(type="time-tile", column=ALL, row=ALL), "n_clicks"),
     Input('datepicker', 'date'), Input(dict(type="delete-booking", bookingid=ALL), "n_clicks")],
    [State("selection_store", "data"), State("datepicker", "date")]
)
def erik(clear, book, k, dd, ff, data, date):
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

            new_booking = create_from_to(data["f"], data["t"])

            if np.any((bookings + new_booking) > config.MAX):
                msg = "Booking interval is overlapping with a full time slot"
            elif np.any((new_booking + my_bookings) > 1):
                msg = "Booking interval is overlapping with a previous booking"
            else:
                db.session.add(Booking(start=b_start, end=b_end, user=current_user.id))
                db.session.commit()
                msg = "Booking successfully created"
                msg_color = "success"
            data = {"f": None, "t": None}
        else:
            msg = "Data is wierd..."
    elif isinstance(trig.id, dict):
        if trig.id["type"] == "time-tile":
            new_click = trig.id["row"] * config.COLUMNS * 4 + trig.id["column"]
            if data["f"] and data["t"] or data["f"] is None:
                data["f"] = new_click
                data["t"] = None
            elif data["t"] is None:
                if (new_click - data["f"]) > (3*4 - 1):
                    data["t"] = data["f"] + (3*4 - 1)
                    msg = "You can maximally choose 3 hours"
                    msg_color = "warning"
                else:
                    data["t"] = new_click
        elif trig.id["type"] == "delete-booking":
            db.session.delete(db.session.query(Booking).filter_by(id=trig.id["bookingid"]).first())
            db.session.commit()

    return html.Table(create_rows(d, data["f"], data["t"]), style={"border-collapse": "collapse"}), \
           data, msg, msg_color, msg != "", create_bookings()





def create_bookings():
    k = dbc.ListGroup([
        dbc.ListGroupItem([
            dbc.Row([
                dbc.Col([
                    dbc.Row(b.start.date()),
                    dbc.Row([
                        f'{b.start.strftime("%H:%M")} - {b.end.strftime("%H:%M")}'
                    ])
                ], width=6),
                dbc.Col(
                    dbc.Button("Delete", id=dict(type="delete-booking", bookingid=b.id)),
                    width=6
                )
            ])
        ]) for b in db.session.query(Booking).filter_by(user=current_user.id).all()
    ])
    return k


app.layout = html.Div([
    dcc.Store(id="selection_store", data={"f": None, "t": None}),
    dcc.Store(id="bookings_store", data={}),
    dbc.Row([
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
                            className="m-1"
                        ),
                    ]),


                ], justify="between", className="my-3"),
                dbc.Row([
                    html.Div([
                        html.Table(create_rows(datetime.now().date(), None, None), style={"border-collapse": "collapse"})
                    ], id="main", className="my-3"),
                ], justify="around"),
                dbc.Row([
                    dbc.Col([
                        html.Table([
                            html.Tr([
                                html.Td([
                                    "Booked"
                                ], style={"background-color": "green", "color": "white", "font-weight": "bold"}),
                            ]),
                            html.Tr([
                                html.Td([
                                    "Selected"
                                ], style={"background-color": "grey", "color": "white", "font-weight": "bold"}),
                            ]),
                            html.Tr([
                                html.Td([
                                    "Available"
                                ], style={"background-color": "blue", "color": "white", "font-weight": "bold"}),
                            ]),
                            html.Tr([
                                html.Td([
                                    "Full"
                                ], style={"background-color": "Red", "color": "white", "font-weight": "bold"}),
                            ]),
                            html.Tr([
                                html.Td([
                                    "Almost full"
                                ], style={"background-color": "orange", "color": "white", "font-weight": "bold"})
                            ])
                        ])
                    ], width=2),
                    dbc.Col([dbc.Alert(id="msg", is_open=False)], width=7),
                    dbc.Col([dbc.Row([
                        dbc.Button("Clear selection", id="clear", className="mx-1", color="primary"),
                        dbc.Button("Book", id="book", color="success"),
                    ])], width=3)
                ])
            ])
        ], width=7),
        dbc.Col([
            dbc.Row([dbc.Label("My bookings")]),
            dbc.Row(id="my-bookings")
        ], width=3)
    ])
])

for view_func in fapp.view_functions:
    if view_func.startswith('/'):
        fapp.view_functions[view_func] = login_required(fapp.view_functions[view_func])


if __name__ == '__main__':

    if not User.query.filter_by(username="admin").first():
        print("Creating admin user")
        db.session.add(User(
            active=True,
            username="admin",
            email=os.getenv("ADMIN_EMAIL", "gedemagt+bookingadmin@gmail.com"),
            email_confirmed_at=datetime.now(),
            password=user_manager.password_manager.hash_password(os.getenv("ADMIN_PASS", "changeme")),
            role="ADMIN"
        ))
        db.session.commit()
    app.run_server(debug=True)
