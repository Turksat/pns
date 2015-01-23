# -*- coding: utf-8 -*-

import logging
import pika
from sqlalchemy.sql.expression import false
from flask.json import loads, dumps
from pns.utils import get_conf, get_logging_handler
from pns.models import db, User, Device, Channel


conf = get_conf()
chunk_size = 1000

# configure logger
logger = logging.getLogger(__name__)
logger.addHandler(get_logging_handler())
if conf.getboolean('application', 'debug'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

# rabbitmq configuration
credentials = pika.credentials.PlainCredentials(
    username=conf.get('rabbitmq', 'username'),
    password=conf.get('rabbitmq', 'password'))
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=conf.get('rabbitmq', 'host'),
                              heartbeat_interval=conf.getint('rabbitmq', 'worker_heartbeat_interval'),
                              credentials=credentials))
channel = connection.channel()
channel.exchange_declare(exchange='pns_exchange', type='direct', durable=True)
channel.queue_declare(queue='pns_pre_processing_queue', durable=True)
channel.queue_bind(exchange='pns_exchange', queue='pns_pre_processing_queue', routing_key='pns_pre_processing')


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def callback(ch, method, properties, body):
    """get device list and divide chunks according to platform type (APNS and GCM)
    GCM broadcasting calls allow only 1000 recipients at one time. Follow same size for APNS work load.
    """
    message = loads(body)
    logger.debug('message: %s' % message)
    if 'pns_id' in message['payload'] and len(message['payload']['pns_id']):
        if conf.getboolean('apns', 'enabled'):
            for devices in get_user_devices(message['payload']['pns_id'], 'apns', chunk_size):
                publish_apns(devices, message['payload'])
        if conf.getboolean('gcm', 'enabled'):
            for devices in get_user_devices(message['payload']['pns_id'], 'gcm', chunk_size):
                publish_gcm(devices, message['payload'])
    if 'channel_id' in message and message['channel_id']:
        if conf.getboolean('apns', 'enabled'):
            for devices in get_channel_devices(message['channel_id'], 'apns', chunk_size):
                publish_apns(devices, message['payload'])
        if conf.getboolean('gcm', 'enabled'):
            for devices in get_channel_devices(message['channel_id'], 'gcm', chunk_size):
                publish_gcm(devices, message['payload'])
    ch.basic_ack(delivery_tag=method.delivery_tag)


def get_user_devices(pns_id_list, platform, per_page):
    """ Yield registered devices of users
    """
    for pns_id in chunks(pns_id_list, per_page):
        device_list = (db
                       .session
                       .query(Device.platform_id)
                       .join(User)
                       .filter(User.pns_id.in_(pns_id))
                       .filter(Device.platform == platform)
                       .filter(Device.mute == false())
                       .all())
        if device_list:
            for devices in chunks(device_list, per_page):
                yield map(lambda x: x[0], devices)


def get_channel_devices(channel_id, platform, per_page):
    """ Yield registered devices of channel
    """
    page = 1
    while True:
        device_list = (Channel
                       .query
                       .get(channel_id)
                       .devices
                       .filter(Device.platform == platform)
                       .with_entities(Device.platform_id)
                       .paginate(page=page, per_page=per_page, error_out=False))
        if device_list.items:
            yield map(lambda x: x[0], device_list.items)
            if not device_list.has_next:
                break
        else:
            break
        page += 1


def publish_gcm(gcm_devices, payload):
    channel.basic_publish(exchange='pns_exchange',
                          routing_key='pns_gcm',
                          body=dumps({'devices': gcm_devices, 'payload': payload},
                                     ensure_ascii=False),
                          mandatory=True,
                          properties=pika.BasicProperties(
                              delivery_mode=2,  # make message persistent
                              content_type='application/json'
                          ))


def publish_apns(apns_devices, payload):
    channel.basic_publish(exchange='pns_exchange',
                          routing_key='pns_apns',
                          body=dumps({'devices': apns_devices, 'payload': payload},
                                     ensure_ascii=False),
                          mandatory=True,
                          properties=pika.BasicProperties(
                              delivery_mode=2,  # make message persistent
                              content_type='application/json'
                          ))


channel.basic_qos(prefetch_count=1)
channel.basic_consume(callback, queue='pns_pre_processing_queue')
channel.start_consuming()