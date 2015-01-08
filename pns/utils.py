# -*- coding: utf-8 -*-

import os
import logging
from ConfigParser import ConfigParser
from logging import Formatter, StreamHandler
from logging.handlers import SysLogHandler


def get_logging_handler():
    """get logging handler
    """
    conf = get_conf()
    if conf.getboolean('application', 'debug'):
        handler = StreamHandler()
        handler.setLevel(logging.DEBUG)
    else:
        handler = SysLogHandler(address='/dev/log')
        handler.setLevel(logging.WARNING)
    handler.setFormatter(Formatter(
        'pns %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    return handler


def get_conf():
    """read ini file and get config parameters
    """
    env_var = 'PNSCONF'
    conf_file = os.getenv(env_var, None)
    if not conf_file:
        raise Exception('environment variable `%s` for configuration file is not set' % env_var)
    conf = ConfigParser()
    if os.path.exists(conf_file):
        conf.read(conf_file)
        return conf
    raise IOError('could not able to read file `%s`' % conf_file)