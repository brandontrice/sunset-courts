from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100))
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    family_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(200))
    ban_date = db.Column(db.DateTime)
    ban_lift_date = db.Column(db.DateTime)
    role = db.Column(db.String(20), default='member')  # 'member', 'volunteer', 'admin'

    dues = db.relationship('Dues', backref='member', lazy=True)
    bookings = db.relationship('Booking', backref='member', lazy=True)


class Dues(db.Model):
    __tablename__ = 'dues'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date_paid = db.Column(db.DateTime)
    notes = db.Column(db.String(200))
    status = db.Column(db.String(20), default='unpaid')
    year = db.Column(db.Integer, default=lambda: date.today().year)


class Court(db.Model):
    __tablename__ = 'courts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    court_number = db.Column(db.Integer, unique=True, nullable=False)  # 1–6
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship('Booking', backref='court', lazy=True)
    blocks = db.relationship('CourtBlock', backref='court', lazy=True)


class CourtBlock(db.Model):
    __tablename__ = 'court_blocks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(200))
    block_type = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey('members.id'))


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    has_guest = db.Column(db.Boolean, default=False)
    is_cancelled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    guest = db.relationship('Guest', backref='booking', uselist=False, lazy=True)

    __table_args__ = (
        db.UniqueConstraint('court_id', 'date', 'start_time', name='uq_court_date_start'),
    )


class Guest(db.Model):
    __tablename__ = 'guests'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    booked_by_member = db.Column(db.Integer, db.ForeignKey('members.id'))


def seed_courts():
    if Court.query.count() == 0:
        for i in range(1, 7):
            db.session.add(Court(court_number=i, is_active=True))
        db.session.commit()
