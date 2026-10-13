from flask import Flask
app= Flask(__name__)
app.config.from_object('config')
from database import init_db
init_db(app)
@app.route('/')
def index(): 
    return 'Hoş geldiniz!'
if __name__== '__main':
        app.run(debug=True)
print("kod çalışıyor")


