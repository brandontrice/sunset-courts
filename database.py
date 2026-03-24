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
    role = db.Column(db.String(20), default='member')

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
    court_number = db.Column(db.Integer, unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship('Booking', backref='court', lazy=True)
    blocks = db.relationship('CourtBlock', backref='court', lazy=True)


class CourtBlock(db.Model):
    __tablename__ = 'court_blocks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.String(200))
    block_type = db.Column(db.String(50))  # 'Maintenance' or 'Special Event'
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


def seed_test_data():
    from datetime import date, time

    if Member.query.count() == 0:
        test_members = [
            Member(first_name='John', last_name='Smith', phone='5401111111',
                   email='john@email.com', role='member'),
            Member(first_name='Jane', last_name='Doe', phone='5402222222',
                   email='jane@email.com', role='member'),
            Member(first_name='Bob', last_name='Johnson', phone='5403333333',
                   email='bob@email.com', role='member'),
            Member(first_name='Sarah', last_name='Williams', phone='5404444444',
                   email='sarah@email.com', role='volunteer'),
            Member(first_name='Mike', last_name='Brown', phone='5405555555',
                   email='mike@email.com', role='member'),
        ]
        for m in test_members:
            db.session.add(m)
        db.session.commit()

    if Booking.query.count() == 0:
        today = date.today()
        test_bookings = [
            Booking(court_id=1, member_id=1, date=today,
                    start_time=time(9, 0), end_time=time(10, 0), is_cancelled=False),
            Booking(court_id=1, member_id=2, date=today,
                    start_time=time(11, 0), end_time=time(12, 30), is_cancelled=False),
            Booking(court_id=2, member_id=3, date=today,
                    start_time=time(10, 0), end_time=time(10, 30), is_cancelled=False),
            Booking(court_id=2, member_id=4, date=today,
                    start_time=time(13, 0), end_time=time(14, 0), is_cancelled=False),
            Booking(court_id=3, member_id=5, date=today,
                    start_time=time(8, 0), end_time=time(9, 0), is_cancelled=False),
            Booking(court_id=3, member_id=1, date=today,
                    start_time=time(14, 0), end_time=time(14, 30), is_cancelled=False),
            Booking(court_id=4, member_id=2, date=today,
                    start_time=time(9, 0), end_time=time(10, 30), is_cancelled=False),
            Booking(court_id=5, member_id=3, date=today,
                    start_time=time(15, 0), end_time=time(16, 0), is_cancelled=False),
            Booking(court_id=6, member_id=4, date=today,
                    start_time=time(10, 0), end_time=time(11, 0),
                    has_guest=True, is_cancelled=False),
        ]
        for b in test_bookings:
            db.session.add(b)
        db.session.commit()
