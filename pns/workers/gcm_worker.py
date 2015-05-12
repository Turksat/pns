# -*- coding: utf-8 -*-

import logging
import pika
from flask.json import loads
from gcm import GCM
from pns.utils import get_conf, get_logging_handler
from pns.models import db, Device


conf = get_conf()

# configure logger
logger = logging.getLogger(__name__)
logger.addHandler(get_logging_handler())
if conf.getboolean('application', 'debug'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

# GCM configuration
gcm = GCM(conf.get('gcm', 'key'))

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
channel.queue_declare(queue='pns_gcm_queue', durable=True)
channel.queue_bind(exchange='pns_exchange', queue='pns_gcm_queue', routing_key='pns_gcm')


def callback(ch, method, properties, body):
    message = loads(body)
    logger.debug('payload: %s' % message)
    collapse_key, delay_while_idle = None, None
    if 'gcm' in message['payload']:
        if 'collapse_key' in message['payload']['gcm']:
            collapse_key = message['payload']['gcm']['collapse_key']
        if 'delay_while_idle' in message['payload']['gcm']:
            delay_while_idle = message['payload']['gcm']['delay_while_idle']
    # time to live (in seconds)
    ttl = None
    if 'ttl' in message['payload']:
        ttl = message['payload']['ttl']
        if ttl > 2419200 or ttl < 0:
            logger.warning('`time_to_live` is out of boundary')
            # use default value
            ttl = None
    if 'data' not in message['payload']:
        message['payload']['data'] = {}
    message['payload']['data']['alert'] = message['payload']['alert']
    try:
        response = gcm.json_request(registration_ids=message['devices'],
                                    data=message['payload']['data'],
                                    collapse_key=collapse_key,
                                    delay_while_idle=delay_while_idle,
                                    time_to_live=ttl)
    except Exception as ex:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.exception(ex)
        return
    logger.debug('gcm response: %s' % response)
    # Handling errors
    if 'errors' in response:
        for error, reg_ids in response['errors'].items():
            # Check for errors and act accordingly
            if error in ['NotRegistered', 'InvalidRegistration']:
                # Remove reg_ids from database
                for reg_id in reg_ids:
                    device_obj = Device.query.filter_by(platform_id=reg_id).first()
                    if device_obj:
                        db.session.delete(device_obj)
        try:
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            logger.exception(ex)
    if 'canonical' in response:
        for reg_id, canonical_id in response['canonical'].items():
            # Replace reg_id with canonical_id in your database
            device_obj = Device.query.filter_by(platform_id=reg_id).first()
            if device_obj:
                if Device.query.filter_by(platform_id=canonical_id).first():
                    # canonical_id has already registered by client, just delete stale reg_id
                    db.session.delete(device_obj)
                else:
                    # replace with canonical_id
                    device_obj.platform_id = canonical_id
                    db.session.add(device_obj)
                try:
                    db.session.commit()
                except Exception as ex:
                    db.session.rollback()
                    logger.exception(ex)
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_count=1)
channel.basic_consume(callback, queue='pns_gcm_queue')
channel.start_consuming()