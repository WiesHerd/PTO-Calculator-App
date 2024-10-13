from flask_frozen import Freezer
from app import app

app.config['FREEZER_STATIC_FILES'] = ['static/js/app.js']

freezer = Freezer(app)

if __name__ == '__main__':
    freezer.freeze()
