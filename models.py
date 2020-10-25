from flask_sqlalchemy import SQLAlchemy
from flask_user import UserMixin

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


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, default=1)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)

    user_id = db.Column(db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'))
    gym_id = db.Column(db.Integer(), db.ForeignKey('gyms.id', ondelete='CASCADE'), nullable=False)


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

    admins = db.relationship('User', secondary=gym_admins, lazy='subquery',
                             backref=db.backref('admin_gyms', lazy=True))

    users = db.relationship('User', secondary=gym_memberships, lazy='subquery',
                             backref=db.backref('gyms', lazy=True))

    bookings = db.relationship('Booking', backref=db.backref('gym', lazy=True))


