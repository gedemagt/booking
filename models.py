import os
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_user import UserMixin
from wtforms import ValidationError

from app import fapp
from custom import CustomUserManager

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
    max_number_per_booking = db.Column(db.Integer, nullable=False, default=1)
    max_people = db.Column(db.Integer, nullable=False, default=10)
    max_booking_length = db.Column(db.Integer, nullable=True)
    max_booking_per_user = db.Column(db.Integer, nullable=True)
    max_time_per_user_per_day = db.Column(db.Integer, nullable=True)

    admins = db.relationship('User', secondary=gym_admins, lazy='subquery',
                             backref=db.backref('admin_gyms', lazy=True))

    users = db.relationship('User', secondary=gym_memberships, lazy='subquery',
                             backref=db.backref('gyms', lazy=True))

    bookings = db.relationship('Booking', backref=db.backref('gym', lazy=True))


user_manager = CustomUserManager(fapp, db, UserClass=User)


if not os.path.exists(fapp.config['SQLALCHEMY_DATABASE_URI'].split("/")[-1]):
    print("Initializing database")

    db.create_all()

    g = Gym(name="TestGym", code="TestGym")

    admin = User(
        active=True,
        username="admin",
        email_confirmed_at=datetime.now(),
        email=os.getenv("ADMIN_EMAIL", "gedemagt+bookingadmin@gmail.com"),
        password=user_manager.password_manager.hash_password(os.getenv("ADMIN_PASS", "changeme")),
        role="ADMIN",
    )

    g.admins.append(admin)
    admin.gyms.append(g)

    db.session.add(g)
    db.session.add(admin)
    db.session.commit()

