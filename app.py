# 'flash' added to 'from flask import' to allow alert boxes configured in Members.html - Added by Channing
from flask import Flask, render_template, send_file, redirect, url_for, request, jsonify, flash
# Added 'Banlog' and 'InactiveLog' to 'from database import' - Added by Channing
from database import db, Member, Dues, Court, CourtBlock, Booking, Guest, BanLog, InactiveLog, seed_courts, seed_test_data
import csv
import os
import re
from datetime import datetime, date, timedelta, time

# APScheduler for weekly auto-export
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

# Sanitization for member phone numbers - Added by Channing
def sanitize_phone(phone):
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    if len(cleaned) < 7 or len(cleaned) > 20:
        raise ValueError("Invalid phone number")
    return cleaned

# Sanitization for member names - Added by Channing
def sanitize_name(name):
    name = name.strip()
    if not name or len(name) > 50:
        raise ValueError("Invalid name")
    return name

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


# ── Shared export logic ───────────────────────────────────────────────────────

def run_export():
    """Write a timestamped CSV backup. Called manually and by the scheduler."""
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_folder, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'sunset_courts_backup_{timestamp}.csv'
    filepath = os.path.join(backup_folder, filename)

    with app.app_context():
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

    print(f'[Scheduler] Backup written: {filename}')
    return filename


def next_sunday_11pm():
    """Return the next Sunday at 23:00 local time."""
    now = datetime.now()
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 23:
        days_until_sunday = 7
    target = now + timedelta(days=days_until_sunday)
    return target.replace(hour=23, minute=0, second=0, microsecond=0)


# ── Scheduler setup ───────────────────────────────────────────────────────────

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=run_export,
    trigger=CronTrigger(day_of_week='sun', hour=23, minute=0),
    id='weekly_backup',
    name='Weekly Sunday 11 PM backup',
    replace_existing=True
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    today = date.today()
    today_display = today.strftime('%B %d, %Y')

    raw_bookings = Booking.query.filter_by(
        date=today,
        is_cancelled=False
    ).order_by(Booking.start_time, Booking.court_id).all()

    bookings = []
    for b in raw_bookings:
        member = Member.query.get(b.member_id)
        court = Court.query.get(b.court_id)
        bookings.append({
            'court_number': court.court_number,
            'member_name': f'{member.first_name} {member.last_name}',
            'start': b.start_time.strftime('%I:%M %p'),
            'end': b.end_time.strftime('%I:%M %p'),
            'has_guest': b.has_guest,
        })

    return render_template('index.html', bookings=bookings, today_display=today_display)


@app.route('/calendar')
def calendar():
    selected_date_str = request.args.get('date', date.today().isoformat())
    selected_date = date.fromisoformat(selected_date_str)

    # ── Year guard: only show bookings for the current year ──────────────────
    current_year = date.today().year
    if selected_date.year != current_year:
        # Clamp to Jan 1 or Dec 31 of current year depending on direction
        if selected_date.year > current_year:
            selected_date = date(current_year, 12, 31)
        else:
            selected_date = date(current_year, 1, 1)
        selected_date_str = selected_date.isoformat()

    display_date = selected_date.strftime('%m-%d-%Y')

    # Prev/next still navigate freely but will be clamped on load if out of year
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

    # Active bookings
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
            'booking_id': b.id,
            'member_name': f'{member.first_name} {member.last_name}',
            'start': slot_key,
            'end': f'{b.end_time.hour:02d}:{b.end_time.minute:02d}',
            'rowspan': duration_slots,
            'has_guest': b.has_guest,
        }
        current = start_total
        while current < end_total:
            h = current // 60
            m = current % 60
            booked_cells.add((b.court_id, f'{h:02d}:{m:02d}'))
            current += 30

    cancelled_bookings = Booking.query.filter_by(
        date=selected_date,
        is_cancelled=True
    ).all()

    cancelled_map = {}
    cancelled_cells = set()
    for b in cancelled_bookings:
        member = Member.query.get(b.member_id)
        start_total = b.start_time.hour * 60 + b.start_time.minute
        end_total = b.end_time.hour * 60 + b.end_time.minute
        duration_slots = (end_total - start_total) // 30
        slot_key = f'{b.start_time.hour:02d}:{b.start_time.minute:02d}'
        if (b.court_id, slot_key) not in cancelled_map:
            cancelled_map[(b.court_id, slot_key)] = {
                'booking_id': b.id,
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
                cancelled_cells.add((b.court_id, f'{h:02d}:{m:02d}'))
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
                           current_year=current_year,
                           time_slots=time_slots,
                           booking_map=booking_map,
                           booked_cells=booked_cells,
                           cancelled_map=cancelled_map,
                           cancelled_cells=cancelled_cells,
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
            all_courts = Court.query.filter_by(is_active=True).all()
            available_courts = []
            for c in all_courts:
                if c.id == court_id:
                    continue
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


@app.route('/bookings/cancel/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    redirect_date = booking.date.isoformat()
    booking.is_cancelled = True
    db.session.commit()
    return redirect(url_for('calendar', date=redirect_date))


@app.route('/bookings')
def booking():
    courts = Court.query.filter_by(is_active=True).all()
    return render_template('booking.html', courts=courts)


@app.route('/member/by-phone/<phone>')
def get_member(phone):
    members = Member.query.filter_by(phone=phone).all()
    if not members:
        return jsonify({'error': 'No member found with that phone number.'}), 404

    results = []
    for m in members:
        if not m.is_active or m.is_banned:
            continue
        results.append({
            'id': m.id,
            'name': f'{m.first_name} {m.last_name}',
            'email': m.email,
            'role': m.role
        })

    if not results:
        return jsonify({'error': 'Member found but not eligible to book (inactive or banned).'}), 404

    return jsonify({'members': results})


@app.route('/bookings/add', methods=['POST'])
def add_booking():
    data = request.get_json()

    member_id = data.get('member_id')
    court_id = int(data.get('court_id'))
    booking_date = date.fromisoformat(data.get('date'))
    start_time = datetime.strptime(data.get('start_time'), '%H:%M').time()
    end_time = datetime.strptime(data.get('end_time'), '%H:%M').time()
    has_guest = bool(data.get('has_guest', False))

    # Reject past dates
    if booking_date < date.today():
        return jsonify({'error': 'Cannot book a date in the past.'}), 400

    # Restrict to current year only
    current_year = date.today().year
    if booking_date.year != current_year:
        return jsonify({'error': f'Bookings are only allowed within {current_year}.'}), 400

    start_total = start_time.hour * 60 + start_time.minute
    end_total = end_time.hour * 60 + end_time.minute

    existing = Booking.query.filter_by(
        court_id=court_id,
        date=booking_date,
        is_cancelled=False
    ).all()

    for b in existing:
        b_start = b.start_time.hour * 60 + b.start_time.minute
        b_end = b.end_time.hour * 60 + b.end_time.minute
        if b_start < end_total and b_end > start_total:
            return jsonify({'error': 'That court is already booked during that time.'}), 409

    blocks = CourtBlock.query.filter_by(court_id=court_id, date=booking_date).all()
    for bl in blocks:
        bl_start = bl.start_time.hour * 60 + bl.start_time.minute
        bl_end = bl.end_time.hour * 60 + bl.end_time.minute
        if bl_start < end_total and bl_end > start_total:
            covering_cancel = Booking.query.filter_by(
                court_id=court_id,
                date=booking_date,
                is_cancelled=True
            ).all()
            slot_has_cancel = any(
                (cb.start_time.hour * 60 + cb.start_time.minute) <= start_total and
                (cb.end_time.hour * 60 + cb.end_time.minute) >= end_total
                for cb in covering_cancel
            )
            if not slot_has_cancel:
                return jsonify({'error': 'That court is blocked during that time.'}), 409

    # Do NOT delete cancelled bookings that share this slot — they are preserved
    # as history and rendered alongside the new active booking in a split column
    # on the calendar. The UniqueConstraint on (court_id, date, start_time) was
    # already removed from the model, so the insert below will succeed cleanly.

    new_booking = Booking(
        court_id=court_id,
        member_id=member_id,
        date=booking_date,
        start_time=start_time,
        end_time=end_time,
        has_guest=has_guest
    )
    db.session.add(new_booking)
    db.session.commit()

    return jsonify({'success': True, 'booking_id': new_booking.id})


@app.route('/export')
def export():
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_folder, exist_ok=True)
    all_files = sorted(
        [f for f in os.listdir(backup_folder) if f.endswith('.csv')],
        reverse=True
    )

    latest = all_files[0] if all_files else None
    previous = all_files[1:] if len(all_files) > 1 else []
    next_backup = next_sunday_11pm()
    next_backup_display = next_backup.strftime('%A, %B %d, %Y at %I:%M %p')

    return render_template('export.html',
                           latest=latest,
                           previous=previous,
                           next_backup_display=next_backup_display)


@app.route('/export/download')
def export_download():
    run_export()
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


@app.route('/export/clear', methods=['POST'])
def clear_backups():
    """Delete all backups except the most recent one."""
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    all_files = sorted(
        [f for f in os.listdir(backup_folder) if f.endswith('.csv')],
        reverse=True
    )
    # Keep the latest, delete the rest
    deleted = 0
    for f in all_files[1:]:
        try:
            os.remove(os.path.join(backup_folder, f))
            deleted += 1
        except OSError:
            pass
    return redirect(url_for('export'))


# Members list + search - Added by Channing
@app.route('/members')
def members():
    search_term   = request.args.get('search', '').strip()
    status_filter = request.args.get('status_filter', 'all')

    query = Member.query

    # Search by phone or name
    if search_term:
        query = query.filter(
            (Member.phone.ilike(f'%{search_term}%')) |
            (Member.first_name.ilike(f'%{search_term}%')) |
            (Member.last_name.ilike(f'%{search_term}%'))
        )

    # Filter by status
    if status_filter == 'active':
        query = query.filter_by(is_active=True, is_banned=False)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False, is_banned=False)
    elif status_filter == 'banned':
        query = query.filter_by(is_banned=True)

    members       = query.order_by(Member.last_name, Member.first_name).all()
    all_members   = Member.query.order_by(Member.last_name).all()  # for JS edit modal

    return render_template('members.html',
                           members=members,
                           all_members=all_members,
                           search_term=search_term,
                           status_filter=status_filter,
                           today=date.today().isoformat())


# Add a new member - Added by Channing
@app.route('/members/add', methods=['POST'])
def add_member():
    try:
        first_name  = sanitize_name(request.form.get('first_name', ''))
        last_name   = sanitize_name(request.form.get('last_name', ''))
        phone       = sanitize_phone(request.form.get('phone', ''))
        email       = request.form.get('email', '').strip()
        join_date_str = request.form.get('join_date', '')

        # Parse join date
        join_date = datetime.strptime(join_date_str, '%Y-%m-%d') if join_date_str else datetime.utcnow()

        # Check phone is unique
        if Member.query.filter_by(phone=phone).first():
            flash('A member with that phone number already exists.', 'danger')
            return redirect(url_for('members'))

        if role not in ('member', 'volunteer'):
            role = 'member'

        new_member = Member(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            join_date=join_date,
            is_active=True,
            is_banned=False
        )
        db.session.add(new_member)
        db.session.commit()
        flash(f'{first_name} {last_name} added successfully.', 'success')

    except ValueError as e:
        flash(f'Invalid input: {e}', 'danger')
    except Exception:
        db.session.rollback()
        flash('Something went wrong. Please try again.', 'danger')

    return redirect(url_for('members'))


# Edit a member - Added by Channing
@app.route('/members/edit', methods=['POST'])
def edit_member():
    try:
        member_id   = int(request.form.get('member_id'))
        member      = Member.query.get_or_404(member_id)
        first_name  = sanitize_name(request.form.get('first_name', ''))
        last_name   = sanitize_name(request.form.get('last_name', ''))
        phone       = sanitize_phone(request.form.get('phone', ''))
        email       = request.form.get('email', '').strip()
        join_date_str = request.form.get('join_date', '')

        # Check phone uniqueness (allow same member to keep their number)
        existing = Member.query.filter_by(phone=phone).first()
        if existing and existing.id != member_id:
            flash('That phone number belongs to another member.', 'danger')
            return redirect(url_for('members'))

        # Parse join date
        if join_date_str:
            member.join_date = datetime.strptime(join_date_str, '%Y-%m-%d')

        member.first_name  = first_name
        member.last_name   = last_name
        member.phone       = phone           # Task 1
        member.email       = email

        db.session.commit()
        flash(f'{first_name} {last_name} updated successfully.', 'success')

    except ValueError as e:
        flash(f'Invalid input: {e}', 'danger')
    except Exception:
        db.session.rollback()
        flash('Something went wrong. Please try again.', 'danger')

    return redirect(url_for('members'))


# Ban a member (keeps data, logs reason) - Added by Channing
@app.route('/members/ban', methods=['POST'])
def ban_member():
    try:
        member_id  = int(request.form.get('member_id'))
        ban_reason = request.form.get('ban_reason', '').strip()
        banned_by  = request.form.get('banned_by', '').strip()
        ban_lift_date_str = request.form.get('ban_lift_date', '').strip()

        if not ban_reason or len(ban_reason) > 500:
            flash('A valid ban reason is required.', 'danger')
            return redirect(url_for('members'))

        if not banned_by:
            flash('Please enter who is recording this ban.', 'danger')
            return redirect(url_for('members'))

        member = Member.query.get_or_404(member_id)

        # Flag as banned — data is kept, never deleted
        member.is_banned  = True
        member.is_active  = False
        member.ban_reason = ban_reason
        member.ban_date   = datetime.utcnow()

         # Set lift date if provided (temporary ban), otherwise leave as permanent
        member.ban_lift_date = (
            datetime.strptime(ban_lift_date_str, '%Y-%m-%d')
            if ban_lift_date_str else None
        )

        # Log the ban with full details
        log = BanLog(
            member_id=member_id,
            ban_reason=ban_reason,
            banned_by=banned_by
        )
        db.session.add(log)
        db.session.commit()
        
        if member.ban_lift_date:
            flash(f'{member.first_name} {member.last_name} has been banned until {member.ban_lift_date.strftime("%m/%d/%Y")}.', 'warning')
        else:
            flash(f'{member.first_name} {member.last_name} has been permanently banned.', 'warning')

    except Exception:
        db.session.rollback()
        flash('Something went wrong. Please try again.', 'danger')

    return redirect(url_for('members'))


# View ban log for a member (AJAX) - Added by Channing
@app.route('/members/ban-log/<int:member_id>')
def get_ban_log(member_id):
    logs = BanLog.query.filter_by(member_id=member_id)\
                       .order_by(BanLog.banned_at.desc()).all()
    return jsonify({
        'logs': [{
            'ban_reason': log.ban_reason,
            'banned_by':  log.banned_by,
            'banned_at':  log.banned_at.strftime('%m/%d/%Y %I:%M %p')
        } for log in logs]
    })


# Deactivate a member (visual element + keeps data) - Added by Channing
@app.route('/members/deactivate', methods=['POST'])
def deactivate_member():
    try:
        member_id   = int(request.form.get('member_id'))
        reason      = request.form.get('reason', '').strip()
        recorded_by = request.form.get('recorded_by', '').strip()

        if not reason or len(reason) > 500:
            flash('A valid reason is required.', 'danger')
            return redirect(url_for('members'))

        if not recorded_by:
            flash('Please enter who is recording this.', 'danger')
            return redirect(url_for('members'))

        member = Member.query.get_or_404(member_id)

        # Close any current inactive reason
        InactiveLog.query.filter_by(
            member_id=member_id,
            is_current=True
        ).update({'is_current': False})

        # Mark inactive — data is kept
        member.is_active = False

        log = InactiveLog(
            member_id=member_id,
            reason=reason,
            recorded_by=recorded_by
        )
        db.session.add(log)
        db.session.commit()
        flash(f'{member.first_name} {member.last_name} has been deactivated.', 'warning')

    except Exception:
        db.session.rollback()
        flash('Something went wrong. Please try again.', 'danger')

    return redirect(url_for('members'))


# Reactivate a member (AJAX) - Added by Channing
@app.route('/members/reactivate/<int:member_id>', methods=['POST'])
def reactivate_member(member_id):
    try:
        member = Member.query.get_or_404(member_id)

        if member.is_banned:
            return jsonify({'error': 'Cannot reactivate a banned member'}), 400

        # Close current inactive log entry
        InactiveLog.query.filter_by(
            member_id=member_id,
            is_current=True
        ).update({'is_current': False})

        member.is_active = True
        db.session.commit()
        return jsonify({'success': True})

    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Something went wrong'}), 500


if __name__ == '__main__':
    app.run(debug=True)
