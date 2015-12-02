# -*- coding: utf-8 -*-

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from pns.utils import get_conf, get_logging_handler

__version__ = '3.4.1'

app = Flask(__name__)
conf = get_conf()

if conf.getboolean('application', 'debug'):
    app.config.from_object('pns.config.DevelopmentConfig')
else:
    app.config.from_object('pns.config.ProductionConfig')

app.logger.addHandler(get_logging_handler())
db = SQLAlchemy(app)