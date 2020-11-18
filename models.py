import os
from datetime import datetime

from flask_migrate import stamp, upgrade
from flask_sqlalchemy import SQLAlchemy
from flask_user import UserMixin

from config import DB_PATH

db = SQLAlchemy()

gym_admins = db.Table(
    'gym_admins',
    db.Column('user', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('gym', db.Integer, db.ForeignKey('gyms.id'), primary_key=True)
)

gym_memberships = db.Table(
    'gym_memberships',
    db.Column('user', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('gym', db.Integer, db.ForeignKey('gyms.id'), primary_key=True)
)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column('is_active', db.Boolean(), nullable=False, server_default='1')
    username = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)
    email = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)
    email_confirmed_at = db.Column(db.DateTime())
    password = db.Column(db.String(255), nullable=False, server_default='')
    role = db.Column(db.String(100, collation='NOCASE'), nullable=False, default="USER")

    bookings = db.relationship('Booking', backref=db.backref('user', lazy=True))

    def __eq__(self, other):
        return other is not None and self.id == other.id


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, default=1)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)

    note = db.Column(db.String, nullable=True)

    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    zone_id = db.Column(db.Integer(), db.ForeignKey('zones.id'), nullable=False)


class Gym(db.Model):
    __tablename__ = 'gyms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    code = db.Column(db.String, nullable=False, unique=True)

    max_people = db.Column(db.Integer, nullable=False, default=10)
    max_booking_length = db.Column(db.Integer, nullable=True) # Number of timeslots
    max_booking_per_user = db.Column(db.Integer, nullable=True) # Number of active bookings
    max_time_per_user_per_day = db.Column(db.Integer, nullable=True) # Number of active bookings on one day
    max_number_per_booking = db.Column(db.Integer, nullable=False, default=1) # Number of persons per booking
    max_days_ahead = db.Column(db.Integer, nullable=True)
    book_before = db.Column(db.Integer, nullable=False, default=0)

    admins = db.relationship('User', secondary=gym_admins, lazy='subquery',
                             backref=db.backref('admin_gyms', lazy=True))

    users = db.relationship('User', secondary=gym_memberships, lazy='subquery',
                             backref=db.backref('gyms', lazy=True))

    zones = db.relationship('Zone', backref=db.backref('gym', lazy=True))

    def get_max_people(self, zone_id):
        try:
            r = next(x for x in self.zones if x.id == zone_id).max_people
            if r is None:
                return self.max_people
            return r
        except StopIteration:
            return self.max_people


class Zone(db.Model):
    __tablename__ = 'zones'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)

    gym_id = db.Column(db.Integer(), db.ForeignKey('gyms.id', ondelete='CASCADE'), nullable=False)

    max_people = db.Column(db.Integer)
    # max_booking_length = db.Column(db.Integer, nullable=True) # Number of timeslots
    # max_booking_per_user = db.Column(db.Integer, nullable=True) # Number of active bookings
    # max_time_per_user_per_day = db.Column(db.Integer, nullable=True) # Number of active bookings on one day
    # max_number_per_booking = db.Column(db.Integer, nullable=False, default=1) # Number of persons per booking

    bookings = db.relationship('Booking', backref=db.backref('zone', lazy=True))


def init_db(fapp, user_manager):

    db.init_app(fapp)

    with fapp.app_context():
        if os.path.exists(DB_PATH):
            upgrade()
        else:
            print("Initializing database")
            db.create_all()
            stamp()
            g = Gym(name="TestGym", code="TestGym")

            admin = User(
                active=True,
                username="admin",
                email_confirmed_at=datetime.now(),
                email=os.getenv("ADMIN_EMAIL", "some@email.com"),
                password=user_manager.password_manager.hash_password(os.getenv("ADMIN_PASS", "changeme")),
                role="ADMIN",
            )

            user = User(
                active=True,
                username="user",
                email_confirmed_at=datetime.now(),
                email="no@email.com",
                password=user_manager.password_manager.hash_password("changeme"),
                role="USER",
            )

            g.zones.append(Zone(name="Zone 1"))
            g.zones.append(Zone(name="Zone 2"))
            g.admins.append(admin)
            admin.gyms.append(g)
            user.gyms.append(g)

            db.session.add(g)
            db.session.add(user)
            db.session.add(admin)
            db.session.commit()
