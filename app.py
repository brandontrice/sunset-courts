from flask import Flask, render_template, send_file
from database import db, Member, Dues, Booking
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
    print('Database tables created successfully.')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/export')
def export():
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    files = os.listdir(backup_folder)
    last_backup = max(files) if files else None
    return render_template('export.html', last_backup=last_backup)

@app.route('/export/download')
def export_download():
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'sunset_courts_backup_{timestamp}.csv'
    filepath = os.path.join(backup_folder, filename)

    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Members section
        writer.writerow(['MEMBERS'])
        writer.writerow(['Phone', 'First Name', 'Last Name', 'Email', 
                        'Join Date', 'Status', 'Ban Reason', 'Family Group'])
        members = Member.query.all()
        for m in members:
            writer.writerow([m.phone, m.first_name, m.last_name, m.email,
                           m.join_date, m.status, m.ban_reason, m.family_group])

        # Blank row between sections
        writer.writerow([])

        # Dues section
        writer.writerow(['DUES'])
        writer.writerow(['ID', 'Member Phone', 'Amount', 'Date Paid', 
                        'Notes', 'Status', 'Year'])
        dues = Dues.query.all()
        for d in dues:
            writer.writerow([d.id, d.member_phone, d.amount, d.date_paid,
                           d.notes, d.status, d.year])

        # Blank row between sections
        writer.writerow([])

        # Bookings section
        writer.writerow(['BOOKINGS'])
        writer.writerow(['ID', 'Member Phone', 'Court Number', 'Date', 
                        'Start Time', 'End Time', 'Guest Name', 'Guest Phone', 'Created At'])
        bookings = Booking.query.all()
        for b in bookings:
            writer.writerow([b.id, b.member_phone, b.court_number, b.date,
                           b.start_time, b.end_time, b.guest_name, b.guest_phone, b.created_at])

    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
