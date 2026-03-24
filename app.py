from flask import Flask, render_template, send_file, redirect, url_for, request
from database import db, Member, Dues, Court, CourtBlock, Booking, Guest, seed_courts, seed_test_data
import csv
import os
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sunset_courts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'sunsetcourts2025'

db.init_app(app)

with app.app_context():
    db.create_all()
    seed_courts()
    seed_test_data()
    print('Database tables created successfully.')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/calendar')
def calendar():
    selected_date_str = request.args.get('date', date.today().isoformat())
    selected_date = date.fromisoformat(selected_date_str)

    prev_date = (selected_date - timedelta(days=1)).isoformat()
    next_date = (selected_date + timedelta(days=1)).isoformat()

    # Generate 30-minute time slots from 6:00 AM to 10:00 PM
    time_slots = []
    hour = 6
    minute = 0
    while hour < 22:
        time_slots.append(f'{hour:02d}:{minute:02d}')
        minute += 30
        if minute == 60:
            minute = 0
            hour += 1

    # Query active bookings for selected date
    bookings = Booking.query.filter_by(
        date=selected_date,
        is_cancelled=False
    ).all()

    # Build a lookup: {(court_id, 'HH:MM'): booking}
    booking_map = {}
    booked_cells = set()
    for b in bookings:
        member = Member.query.get(b.member_id)
        start_hour = b.start_time.hour
        start_min = b.start_time.minute
        end_hour = b.end_time.hour
        end_min = b.end_time.minute
        start_total = start_hour * 60 + start_min
        end_total = end_hour * 60 + end_min
        duration_slots = (end_total - start_total) // 30
        slot_key = f'{start_hour:02d}:{start_min:02d}'
        booking_map[(b.court_id, slot_key)] = {
            'member_name': f'{member.first_name} {member.last_name}',
            'start': slot_key,
            'end': f'{end_hour:02d}:{end_min:02d}',
            'rowspan': duration_slots,
            'has_guest': b.has_guest
        }
        # Mark all slots this booking occupies so we skip them
        current = start_total
        while current < end_total:
            h = current // 60
            m = current % 60
            booked_cells.add((b.court_id, f'{h:02d}:{m:02d}'))
            current += 30

    return render_template('calendar.html',
                           selected_date=selected_date_str,
                           prev_date=prev_date,
                           next_date=next_date,
                           time_slots=time_slots,
                           booking_map=booking_map,
                           booked_cells=booked_cells)


@app.route('/export')
def export():
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_folder, exist_ok=True)
    files = sorted(os.listdir(backup_folder), reverse=True)
    return render_template('export.html', backups=files)


@app.route('/export/download')
def export_download():
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_folder, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'sunset_courts_backup_{timestamp}.csv'
    filepath = os.path.join(backup_folder, filename)

    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Members section
        writer.writerow(['MEMBERS'])
        writer.writerow(['ID', 'Phone', 'First Name', 'Last Name', 'Email',
                         'Join Date', 'Family Name', 'Is Active', 'Is Banned',
                         'Ban Reason', 'Ban Date', 'Ban Lift Date', 'Role'])
        for m in Member.query.all():
            writer.writerow([m.id, m.phone, m.first_name, m.last_name, m.email,
                             m.join_date, m.family_name, m.is_active, m.is_banned,
                             m.ban_reason, m.ban_date, m.ban_lift_date, m.role])

        writer.writerow([])

        # Dues section
        writer.writerow(['DUES'])
        writer.writerow(['ID', 'Member ID', 'Amount', 'Date Paid', 'Notes', 'Status', 'Year'])
        for d in Dues.query.all():
            writer.writerow([d.id, d.member_id, d.amount, d.date_paid,
                             d.notes, d.status, d.year])

        writer.writerow([])

        # Courts section
        writer.writerow(['COURTS'])
        writer.writerow(['ID', 'Court Number', 'Is Active'])
        for c in Court.query.all():
            writer.writerow([c.id, c.court_number, c.is_active])

        writer.writerow([])

        # Court Blocks section
        writer.writerow(['COURT BLOCKS'])
        writer.writerow(['ID', 'Court ID', 'Start Time', 'End Time',
                         'Reason', 'Block Type', 'Created By'])
        for cb in CourtBlock.query.all():
            writer.writerow([cb.id, cb.court_id, cb.start_time, cb.end_time,
                             cb.reason, cb.block_type, cb.created_by])

        writer.writerow([])

        # Bookings section
        writer.writerow(['BOOKINGS'])
        writer.writerow(['ID', 'Court ID', 'Member ID', 'Date', 'Start Time',
                         'End Time', 'Has Guest', 'Is Cancelled', 'Created At'])
        for b in Booking.query.all():
            writer.writerow([b.id, b.court_id, b.member_id, b.date,
                             b.start_time, b.end_time, b.has_guest,
                             b.is_cancelled, b.created_at])

        writer.writerow([])

        # Guests section
        writer.writerow(['GUESTS'])
        writer.writerow(['ID', 'Booking ID', 'First Name', 'Last Name',
                         'Phone', 'Booked By Member'])
        for g in Guest.query.all():
            writer.writerow([g.id, g.booking_id, g.first_name, g.last_name,
                             g.phone, g.booked_by_member])

    return redirect(url_for('export'))


@app.route('/export/backups/<filename>')
def serve_backup(filename):
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    filepath = os.path.join(backup_folder, filename)
    rows = []
    with open(filepath, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            rows.append(row)
    return render_template('view_backup.html', filename=filename, rows=rows)


if __name__ == '__main__':
    app.run(debug=True)
