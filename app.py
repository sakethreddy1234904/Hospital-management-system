from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-this")  # change in production

# Replace credentials if different
DB_USER = "hospital_user"
DB_PASS = "StrongPassword123"
DB_NAME = "hospital_db"
DB_HOST = "localhost"
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(150), nullable=False)
    patient_email = db.Column(db.String(150), nullable=False)
    doctor = db.Column(db.String(150), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # who booked

# --- Add after Appointment model ---
class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(64), unique=True, nullable=False)
    patient_name = db.Column(db.String(150), nullable=False)
    patient_email = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    issued_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # who created the bill

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_number = db.Column(db.String(64), unique=True, nullable=False)
    patient_name = db.Column(db.String(150), nullable=False)
    patient_email = db.Column(db.String(150), nullable=False)
    doctor = db.Column(db.String(150), nullable=False)
    medicines = db.Column(db.Text, nullable=False)  # comma/newline separated list
    notes = db.Column(db.Text, nullable=True)
    issued_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # who created


# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        if not (name and email and password):
            flash("Please fill all fields", "danger")
            return redirect(url_for('register'))
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("User already exists. Please login.", "warning")
            return redirect(url_for('login'))
        pw_hash = generate_password_hash(password)
        user = User(name=name, email=email, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
        flash("Registered successfully. Login now.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash(f"Welcome, {user.name}", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid credentials", "danger")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('login'))

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first.", "warning")
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(Appointment.appointment_date).all()
    return render_template('dashboard.html', appointments=appointments)

@app.route('/book', methods=['GET','POST'])
@login_required
def book():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name').strip()
        patient_email = request.form.get('patient_email').strip().lower()
        doctor = request.form.get('doctor').strip()
        date_str = request.form.get('appointment_date').strip()
        reason = request.form.get('reason').strip()
        if not (patient_name and patient_email and doctor and date_str):
            flash("Please fill required fields", "danger")
            return redirect(url_for('book'))
        try:
            # expected input like: YYYY-MM-DD HH:MM or YYYY-MM-DD
            appointment_date = datetime.fromisoformat(date_str)
        except Exception:
            try:
                appointment_date = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                flash("Invalid date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM", "danger")
                return redirect(url_for('book'))
        appt = Appointment(
            patient_name=patient_name, patient_email=patient_email,
            doctor=doctor, appointment_date=appointment_date, reason=reason,
            user_id=session['user_id']
        )
        db.session.add(appt)
        db.session.commit()
        flash("Appointment booked!", "success")
        return redirect(url_for('dashboard'))
    return render_template('book_appointment.html')

# --- Bills routes ---
@app.route('/bills')
@login_required
def bills():
    user_id = session['user_id']
    bills = Bill.query.filter_by(user_id=user_id).order_by(Bill.issued_date.desc()).all()
    return render_template('bills.html', bills=bills)

@app.route('/bills/add', methods=['GET','POST'])
@login_required
def add_bill():
    if request.method == 'POST':
        bill_number = request.form.get('bill_number').strip()
        patient_name = request.form.get('patient_name').strip()
        patient_email = request.form.get('patient_email').strip().lower()
        amount = request.form.get('amount').strip()
        description = request.form.get('description','').strip()
        if not (bill_number and patient_name and patient_email and amount):
            flash("Please fill required fields", "danger")
            return redirect(url_for('add_bill'))
        try:
            amount_val = float(amount)
        except ValueError:
            flash("Invalid amount", "danger")
            return redirect(url_for('add_bill'))
        b = Bill(
            bill_number=bill_number,
            patient_name=patient_name,
            patient_email=patient_email,
            amount=amount_val,
            description=description,
            user_id=session['user_id']
        )
        db.session.add(b)
        db.session.commit()
        flash("Bill saved.", "success")
        return redirect(url_for('bills'))
    return render_template('add_bill.html')


# --- Prescriptions routes ---
@app.route('/prescriptions')
@login_required
def prescriptions():
    user_id = session['user_id']
    pres = Prescription.query.filter_by(user_id=user_id).order_by(Prescription.issued_date.desc()).all()
    return render_template('prescriptions.html', prescriptions=pres)

@app.route('/prescriptions/add', methods=['GET','POST'])
@login_required
def add_prescription():
    if request.method == 'POST':
        pres_no = request.form.get('prescription_number').strip()
        patient_name = request.form.get('patient_name').strip()
        patient_email = request.form.get('patient_email').strip().lower()
        doctor = request.form.get('doctor').strip()
        medicines = request.form.get('medicines').strip()
        notes = request.form.get('notes','').strip()
        if not (pres_no and patient_name and patient_email and doctor and medicines):
            flash("Please fill required fields", "danger")
            return redirect(url_for('add_prescription'))
        p = Prescription(
            prescription_number=pres_no,
            patient_name=patient_name,
            patient_email=patient_email,
            doctor=doctor,
            medicines=medicines,
            notes=notes,
            user_id=session['user_id']
        )
        db.session.add(p)
        db.session.commit()
        flash("Prescription saved.", "success")
        return redirect(url_for('prescriptions'))
    return render_template('add_prescription.html')


# Run app
if __name__ == "__main__":
    with app.app_context():
        try:
            db.create_all()
            print("Tables created successfully!")
        except Exception as e:
            print(f"Database setup error: {e}")
            raise  # Re-raise to see full traceback
    app.run(debug=True)
