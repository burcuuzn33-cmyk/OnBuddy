from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(_name_)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///onbuddy.db'
db = SQLAlchemy(app)

# Veritabanı modeli (Örnek: Yeni Başlayanlar)
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)

@app.route('/')
def index():
    return render_template('index.html')

if _name_ == '_main_':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
