from flask import Flask, render_template
from database import db

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

if __name__ == '__main__':
    app.run(debug=True)
