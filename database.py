from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Member(db.Model):
	__tablename__ = 'members'
	phone = db.Column(db.String(20), primary_key=True)
	first_name = db.Column(db.String(50), nullable=False)
	last_name = db.Column(db.String(50), nullable=False)
	email = db.Column(db.String(100))
	join_date = db.Column(db.DateTime, default=datetime.utcnow)
	status = db.Column(db.String(20), default='active')
	ban_reason = db.Column(db.String(200))
	family_group = db.Column(db.String(100))
	dues = db.relationship('Dues', backref='member', lazy=True)
	bookings = db.relationship('Booking', backref='member', lazy=True)


class Dues(db.Model):
	__tablename__ = 'dues'
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	member_phone = db.Column(db.String(20), db.ForeignKey('members.phone'), nullable=False)
	amount = db.Column(db.Float, nullable=False)
	date_paid = db.Column(db.DateTime)
	notes = db.Column(db.String(200))
	status = db.Column(db.String(20), default='unpaid')
	year = db.Column(db.Integer, default=datetime.utcnow().year)

class Booking(db.Model):
	__tablename__ = 'bookings'
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	member_phone = db.Column(db.String(20), db.ForeignKey('members.phone'), nullable=False)
	court_number = db.Column(db.Integer, nullable=False)
	date = db.Column(db.Date, nullable=False)
	start_time = db.Column(db.Time, nullable=False)
	end_time = db.Column(db.Time, nullable=False)
	guest_name = db.Column(db.String(100))
	guest_phone = db.Column(db.String(20))
	created_at = db.Column(db.DateTime, default=datetime.utcnow)
