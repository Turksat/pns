# -*- coding: utf-8 -*-

from pns.utils import get_conf


conf = get_conf()

POSTGRESQL = ('postgresql://%(username)s:%(password)s@%(host)s:%(port)s/%(database)s' %
              {'username': conf.get('postgresql', 'username'),
               'password': conf.get('postgresql', 'password'),
               'host': conf.get('postgresql', 'host'),
               'port': conf.get('postgresql', 'port'),
               'database': conf.get('postgresql', 'database')})


class Config():
    WTF_CSRF_ENABLED = False
    SECRET_KEY = conf.get('application', 'secret')
    SQLALCHEMY_DATABASE_URI = POSTGRESQL
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    JSONIFY_PRETTYPRINT_REGULAR = False


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = True
