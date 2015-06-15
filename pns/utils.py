# -*- coding: utf-8 -*-

import os
import pika
import logging
from ConfigParser import ConfigParser
from pika.exceptions import ConnectionClosed


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


class PikaConnectionManager:
    """manage RabbitMQ channel
    handle disconnection and refresh connection
    """
    def __init__(self, username=None, password=None, host='localhost', heartbeat_interval=None):
        """
        :param str username: RabbitMQ username
        :param str password: RabbitMQ password
        :param str host: RabbitMQ host address
        :param str heartbeat_interval: How often to send heartbeats

        """
        self.channel = None
        credentials = None
        if username and password:
            credentials = pika.credentials.PlainCredentials(username=username, password=password)
        self.conn_params = pika.ConnectionParameters(host=host,
                                                     heartbeat_interval=heartbeat_interval,
                                                     credentials=credentials)
        self._connect()

    def _connect(self):
        connection = pika.BlockingConnection(self.conn_params)
        self.channel = connection.channel()

    def _disconnect(self):
        try:
            self.channel.connection.close()
        except ConnectionClosed:
            pass

    def basic_publish(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        try:
            return self.channel.basic_publish(*args, **kwargs)
        except ConnectionClosed:
            self._disconnect()
            self._connect()
            return self.channel.basic_publish(*args, **kwargs)
