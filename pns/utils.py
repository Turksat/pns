# -*- coding: utf-8 -*-

import os
import logging
from ConfigParser import ConfigParser


def get_logging_handler():
    """get logging handler
    """
    conf = get_conf()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
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