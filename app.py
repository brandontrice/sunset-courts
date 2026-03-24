from flask import Flask, render_template, send_file
from database import db, Member, Dues, Court, CourtBlock, Booking, Guest, seed_courts
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sunset_courts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'sunsetcourts2025'

db.init_app(app)

with app.app_context():
    db.create_all()
    seed_courts()
    print('Database tables created successfully.')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/export')
def export():
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_folder, exist_ok=True)
    files = os.listdir(backup_folder)
    last_backup = max(files) if files else None
    return render_template('export.html', last_backup=last_backup)


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
        writer.writerow(['ID','Court ID', 'Member ID', 'Date', 'Start Time',
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

    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route('/export/backups/<filename>')
def serve_backup(filename):
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    return send_file(os.path.join(backup_folder, filename), as_attachment=False, mimetype='text/csv')


if __name__ == '__main__':
    app.run(debug=True)
