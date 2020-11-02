import os
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_user import UserMixin

import config
from app import fapp

db = SQLAlchemy(fapp)

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

    admins = db.relationship('User', secondary=gym_admins, lazy='subquery',
                             backref=db.backref('admin_gyms', lazy=True))

    users = db.relationship('User', secondary=gym_memberships, lazy='subquery',
                             backref=db.backref('gyms', lazy=True))

    zones = db.relationship('Zone', backref=db.backref('gym', lazy=True))
    future_limits = db.relationship('FutureGymLimits', backref=db.backref('gym', lazy=True))


class FutureGymLimits(db.Model):
    __tablename__ = 'future_gym_limits'
    id = db.Column(db.Integer, primary_key=True)
    when = db.Column(db.DateTime, nullable=False)

    max_people = db.Column(db.Integer, nullable=True, default=10)
    max_booking_length = db.Column(db.Integer, nullable=True)  # Number of timeslots
    max_booking_per_user = db.Column(db.Integer, nullable=True)  # Number of active bookings
    max_time_per_user_per_day = db.Column(db.Integer, nullable=True)  # Number of active bookings on one day
    max_number_per_booking = db.Column(db.Integer, nullable=False, default=1)  # Number of persons per booking
    max_days_ahead = db.Column(db.Integer, nullable=True)

    gym_id = db.Column(db.Integer(), db.ForeignKey('gyms.id'), nullable=False)

    def _get_funny_attribute(self, attribute, start=None):
        if start and len(self.future_limits) > 0:
            for fl in self.future_limits:
                if start > fl.when and getattr(fl, attribute) is not None:
                    return getattr(fl, attribute)

        return getattr(self, attribute)

    def get_max_booking_length(self, start=None):
        self._get_funny_attribute("max_booking_length", start)

    def get_max_booking_per_user(self, start=None):
        self._get_funny_attribute("max_booking_per_user", start)

    def get_max_time_per_user_per_day(self, start=None):
        self._get_funny_attribute("max_time_per_user_per_day", start)

    def get_max_number_per_booking(self, start=None):
        self._get_funny_attribute("max_number_per_booking", start)

    def get_max_days_ahead(self, start=None):
        self._get_funny_attribute("max_days_ahead", start)


class Zone(db.Model):
    __tablename__ = 'zones'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)

    gym_id = db.Column(db.Integer(), db.ForeignKey('gyms.id', ondelete='CASCADE'), nullable=False)

    max_people = db.Column(db.Integer)

    bookings = db.relationship('Booking', backref=db.backref('zone', lazy=True))
    future_limits = db.relationship('FutureZoneLimits', backref=db.backref('zone', lazy=True))

    def get_max_people(self, start=None):
        if start and len(self.future_limits) > 0:
            for fl in self.future_limits:
                if start > fl.when and fl.max_people is not None:
                    return fl.max_people

        return self.gym.max_people if self.max_people is None else self.max_people

    def is_open(self, start):
        for fl in self.future_limits:
            if start > fl.when and fl.closes:
                return False
        return True


class FutureZoneLimits(db.Model):
    __tablename__ = 'future_zone_limits'
    id = db.Column(db.Integer, primary_key=True)
    when = db.Column(db.DateTime, nullable=False)
    max_people = db.Column(db.Integer)
    closes = db.Column(db.Boolean, nullable=False, default=False)
    zone_id = db.Column(db.Integer(), db.ForeignKey('zones.id'), nullable=False)


def try_init_db(user_manager):

    db.create_all()
    if Gym.query.filter_by(code="TestGym").first() is None:
        print("Initializing database")

        g = Gym(name="TestGym", code="TestGym")

        admin = User(
            active=True,
            username="admin",
            email_confirmed_at=datetime.now(),
            email=os.getenv("ADMIN_EMAIL", "gedemagt+bookingadmin@gmail.com"),
            password=user_manager.password_manager.hash_password(os.getenv("ADMIN_PASS", "changeme")),
            role="ADMIN",
        )

        g.zones.append(Zone(name="Zone 1"))
        g.zones.append(Zone(name="Zone 2"))
        g.admins.append(admin)
        admin.gyms.append(g)

        db.session.add(g)
        db.session.add(admin)
        db.session.commit()
