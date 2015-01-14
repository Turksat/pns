# -*- coding: utf-8 -*-

import logging
import pika
from sqlalchemy.sql.expression import false
from flask.json import loads, dumps
from pns.utils import get_conf, get_logging_handler
from pns.models import db, User, Device, Channel


conf = get_conf()

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


def callback(ch, method, properties, body):
    """get device list and divide chunks according to platform type (APNS and GCM)
    GCM broadcasting calls allow only 1000 recipients at one time. Follow same size for APNS work load.
    """
    message = loads(body)
    logger.debug('message: %s' % message)
    device_list = []
    if 'pns_id' in message['payload'] and len(message['payload']['pns_id']):
        device_list += (db
                        .session
                        .query(Device.platform, Device.platform_id)
                        .join(User)
                        .filter(User.pns_id.in_(message['payload']['pns_id']))
                        .filter(Device.mute == false())
                        .all())
    if 'channel_id' in message and message['channel_id']:
        user_id_list = Channel.query.get(message['channel_id']).subscribers.with_entities(User.id).all()
        user_id_list = map(lambda x: x[0], user_id_list)
        if len(user_id_list):
            device_list += (db
                            .session
                            .query(Device.platform, Device.platform_id)
                            .join(User)
                            .filter(User.id.in_(user_id_list))
                            .filter(Device.mute == false())
                            .all())
    logger.debug('device count: %s' % len(device_list))
    if not device_list:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return
    # remove duplicates
    device_list = list(set(device_list))
    apns_devices = map(lambda x: x[1], filter(lambda x: x[0] == 'apns', device_list))
    gcm_devices = map(lambda x: x[1], filter(lambda x: x[0] == 'gcm', device_list))
    logger.debug('apns device count: %s' % len(apns_devices))
    logger.debug('apns device list: %s' % apns_devices)
    logger.debug('gcm device count: %s' % len(gcm_devices))
    logger.debug('gcm device list: %s' % gcm_devices)
    if conf.getboolean('apns', 'enabled'):
        publish_apns(apns_devices, message['payload'])
    if conf.getboolean('gcm', 'enabled'):
        publish_gcm(gcm_devices, message['payload'])
    ch.basic_ack(delivery_tag=method.delivery_tag)


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def publish_gcm(gcm_devices, payload):
    if not len(gcm_devices):
        return False
    for devices in list(chunks(gcm_devices, 1000)):
        channel.basic_publish(exchange='pns_exchange',
                              routing_key='pns_gcm',
                              body=dumps({'devices': devices, 'payload': payload},
                                         ensure_ascii=False),
                              mandatory=True,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                                  content_type='application/json'
                              ))


def publish_apns(apns_devices, payload):
    if not len(apns_devices):
        return False
    for devices in list(chunks(apns_devices, 1000)):
        channel.basic_publish(exchange='pns_exchange',
                              routing_key='pns_apns',
                              body=dumps({'devices': devices, 'payload': payload},
                                         ensure_ascii=False),
                              mandatory=True,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                                  content_type='application/json'
                              ))


channel.basic_qos(prefetch_count=1)
channel.basic_consume(callback, queue='pns_pre_processing_queue')
channel.start_consuming()