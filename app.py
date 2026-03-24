from flask import Flask, render_template, send_file, redirect, url_for, request, jsonify
from database import db, Member, Dues, Court, CourtBlock, Booking, Guest, seed_courts, seed_test_data
import csv
import os
from datetime import datetime, date, timedelta, time

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
    display_date = selected_date.strftime('%m-%d-%Y')

    prev_date = (selected_date - timedelta(days=1)).isoformat()
    next_date = (selected_date + timedelta(days=1)).isoformat()

    time_slots = []
    hour = 6
    minute = 0
    while hour < 22:
        time_slots.append(f'{hour:02d}:{minute:02d}')
        minute += 30
        if minute == 60:
            minute = 0
            hour += 1

    bookings = Booking.query.filter_by(
        date=selected_date,
        is_cancelled=False
    ).all()

    booking_map = {}
    booked_cells = set()
    for b in bookings:
        member = Member.query.get(b.member_id)
        start_total = b.start_time.hour * 60 + b.start_time.minute
        end_total = b.end_time.hour * 60 + b.end_time.minute
        duration_slots = (end_total - start_total) // 30
        slot_key = f'{b.start_time.hour:02d}:{b.start_time.minute:02d}'
        booking_map[(b.court_id, slot_key)] = {
            'member_name': f'{member.first_name} {member.last_name}',
            'start': slot_key,
            'end': f'{b.end_time.hour:02d}:{b.end_time.minute:02d}',
            'rowspan': duration_slots,
            'has_guest': b.has_guest
        }
        current = start_total
        while current < end_total:
            h = current // 60
            m = current % 60
            booked_cells.add((b.court_id, f'{h:02d}:{m:02d}'))
            current += 30

    blocks = CourtBlock.query.filter_by(date=selected_date).all()

    block_map = {}
    blocked_cells = set()
    for bl in blocks:
        start_total = bl.start_time.hour * 60 + bl.start_time.minute
        end_total = bl.end_time.hour * 60 + bl.end_time.minute
        duration_slots = (end_total - start_total) // 30
        slot_key = f'{bl.start_time.hour:02d}:{bl.start_time.minute:02d}'
        block_map[(bl.court_id, slot_key)] = {
            'block_id': bl.id,
            'block_type': bl.block_type,
            'reason': bl.reason,
            'start': slot_key,
            'end': f'{bl.end_time.hour:02d}:{bl.end_time.minute:02d}',
            'rowspan': duration_slots
        }
        current = start_total
        while current < end_total:
            h = current // 60
            m = current % 60
            blocked_cells.add((bl.court_id, f'{h:02d}:{m:02d}'))
            current += 30

    return render_template('calendar.html',
                           selected_date=selected_date_str,
                           display_date=display_date,
                           prev_date=prev_date,
                           next_date=next_date,
                           today=date.today().isoformat(),
                           time_slots=time_slots,
                           booking_map=booking_map,
                           booked_cells=booked_cells,
                           block_map=block_map,
                           blocked_cells=blocked_cells)


@app.route('/blocks/check', methods=['POST'])
def check_block_conflicts():
    court_id = int(request.form.get('court_id'))
    block_date = date.fromisoformat(request.form.get('date'))
    start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
    end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()

    start_total = start_time.hour * 60 + start_time.minute
    end_total = end_time.hour * 60 + end_time.minute

    # Find conflicting bookings
    existing_bookings = Booking.query.filter_by(
        court_id=court_id,
        date=block_date,
        is_cancelled=False
    ).all()

    conflicts = []
    for b in existing_bookings:
        b_start = b.start_time.hour * 60 + b.start_time.minute
        b_end = b.end_time.hour * 60 + b.end_time.minute
        if b_start < end_total and b_end > start_total:
            member = Member.query.get(b.member_id)
            # Find available courts for this booking's time slot
            all_courts = Court.query.filter_by(is_active=True).all()
            available_courts = []
            for c in all_courts:
                if c.id == court_id:
                    continue
                # Check no booking exists
                overlap = Booking.query.filter_by(
                    court_id=c.id,
                    date=block_date,
                    is_cancelled=False
                ).all()
                court_free = True
                for ob in overlap:
                    ob_start = ob.start_time.hour * 60 + ob.start_time.minute
                    ob_end = ob.end_time.hour * 60 + ob.end_time.minute
                    if ob_start < b_end and ob_end > b_start:
                        court_free = False
                        break
                # Check no block exists
                block_overlap = CourtBlock.query.filter_by(
                    court_id=c.id,
                    date=block_date
                ).all()
                for bl in block_overlap:
                    bl_start = bl.start_time.hour * 60 + bl.start_time.minute
                    bl_end = bl.end_time.hour * 60 + bl.end_time.minute
                    if bl_start < b_end and bl_end > b_start:
                        court_free = False
                        break
                if court_free:
                    available_courts.append({
                        'id': c.id,
                        'court_number': c.court_number
                    })

            conflicts.append({
                'booking_id': b.id,
                'member_name': f'{member.first_name} {member.last_name}',
                'member_phone': member.phone,
                'start': f'{b.start_time.hour:02d}:{b.start_time.minute:02d}',
                'end': f'{b.end_time.hour:02d}:{b.end_time.minute:02d}',
                'available_courts': available_courts
            })

    return jsonify({
        'conflicts': conflicts,
        'court_id': court_id,
        'date': block_date.isoformat(),
        'start_time': start_time.strftime('%H:%M'),
        'end_time': end_time.strftime('%H:%M')
    })


@app.route('/blocks/add', methods=['POST'])
def add_block():
    court_id = int(request.form.get('court_id'))
    block_date = request.form.get('date')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    block_type = request.form.get('block_type')
    reason = request.form.get('reason')

    start_time = datetime.strptime(start_time_str, '%H:%M').time()
    end_time = datetime.strptime(end_time_str, '%H:%M').time()
    parsed_date = date.fromisoformat(block_date)

    block = CourtBlock(
        court_id=court_id,
        date=parsed_date,
        start_time=start_time,
        end_time=end_time,
        block_type=block_type,
        reason=reason
    )
    db.session.add(block)
    db.session.commit()

    return redirect(url_for('calendar', date=block_date))


@app.route('/blocks/remove/<int:block_id>', methods=['POST'])
def remove_block(block_id):
    block = CourtBlock.query.get_or_404(block_id)
    block_date = block.date.isoformat()
    db.session.delete(block)
    db.session.commit()
    return redirect(url_for('calendar', date=block_date))


@app.route('/bookings/move/<int:booking_id>', methods=['POST'])
def move_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_court_id = int(request.form.get('new_court_id'))
    redirect_date = booking.date.isoformat()
    booking.court_id = new_court_id
    db.session.commit()
    return redirect(url_for('calendar', date=redirect_date))


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

        writer.writerow(['MEMBERS'])
        writer.writerow(['ID', 'Phone', 'First Name', 'Last Name', 'Email',
                         'Join Date', 'Family Name', 'Is Active', 'Is Banned',
                         'Ban Reason', 'Ban Date', 'Ban Lift Date', 'Role'])
        for m in Member.query.all():
            writer.writerow([m.id, m.phone, m.first_name, m.last_name, m.email,
                             m.join_date, m.family_name, m.is_active, m.is_banned,
                             m.ban_reason, m.ban_date, m.ban_lift_date, m.role])

        writer.writerow([])

        writer.writerow(['DUES'])
        writer.writerow(['ID', 'Member ID', 'Amount', 'Date Paid', 'Notes', 'Status', 'Year'])
        for d in Dues.query.all():
            writer.writerow([d.id, d.member_id, d.amount, d.date_paid,
                             d.notes, d.status, d.year])

        writer.writerow([])

        writer.writerow(['COURTS'])
        writer.writerow(['ID', 'Court Number', 'Is Active'])
        for c in Court.query.all():
            writer.writerow([c.id, c.court_number, c.is_active])

        writer.writerow([])

        writer.writerow(['COURT BLOCKS'])
        writer.writerow(['ID', 'Court ID', 'Date', 'Start Time', 'End Time',
                         'Reason', 'Block Type', 'Created By'])
        for cb in CourtBlock.query.all():
            writer.writerow([cb.id, cb.court_id, cb.date, cb.start_time, cb.end_time,
                             cb.reason, cb.block_type, cb.created_by])

        writer.writerow([])

        writer.writerow(['BOOKINGS'])
        writer.writerow(['ID', 'Court ID', 'Member ID', 'Date', 'Start Time',
                         'End Time', 'Has Guest', 'Is Cancelled', 'Created At'])
        for b in Booking.query.all():
            writer.writerow([b.id, b.court_id, b.member_id, b.date,
                             b.start_time, b.end_time, b.has_guest,
                             b.is_cancelled, b.created_at])

        writer.writerow([])

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
