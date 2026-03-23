from flask import Flask
from database import db

app = Flask(__name__)

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sunset_courts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# intialize db
db.init_app(app)

# create tables
with app.app_context():
	db.create_all()
	print('Database tables created succcessfully.')


@app.route('/')
def index():
	return 'Sunset Courts is running!'

if __name__ == '__main__':
	app.run(debug=True)
