# -*- coding: utf-8 -*-

import logging
from flask.json import loads
from gcm import GCM
from pns.utils import get_conf, get_logging_handler, PikaConnectionManager
from pns.models import db, Device


conf = get_conf()

# configure logger
logger = logging.getLogger(__name__)
logger.addHandler(get_logging_handler())
if conf.getboolean('application', 'debug'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)


class GCMWorker(object):
    def __init__(self):
        # GCM configuration
        self.gcm = GCM(conf.get('gcm', 'key'))
        if conf.getboolean('application', 'debug'):
            GCM.enable_logging(logging.DEBUG, get_logging_handler())
        else:
            GCM.enable_logging(logging.ERROR, get_logging_handler())
        # rabbitmq configuration
        self.cm = PikaConnectionManager(username=conf.get('rabbitmq', 'username'),
                                        password=conf.get('rabbitmq', 'password'),
                                        host=conf.get('rabbitmq', 'host'),
                                        heartbeat_interval=conf.getint('rabbitmq', 'worker_heartbeat_interval'))
        self.cm.channel.exchange_declare(exchange='pns_exchange', type='direct', durable=True)
        self.cm.channel.queue_declare(queue='pns_gcm_queue', durable=True)
        self.cm.channel.queue_bind(exchange='pns_exchange', queue='pns_gcm_queue', routing_key='pns_gcm')
        self.cm.channel.basic_qos(prefetch_count=1)
        self.cm.channel.basic_consume(self._callback, queue='pns_gcm_queue')

    def start(self):
        self.cm.channel.start_consuming()

    def _callback(self, ch, method, properties, body):
        """
        send gcm notifications
        :param ch:
        :param method:
        :param properties:
        :param body:
        :return:
        """
        message = loads(body)
        logger.debug('payload: %s' % message)
        collapse_key = None
        delay_while_idle = False
        if 'gcm' in message['payload']:
            if 'collapse_key' in message['payload']['gcm']:
                collapse_key = message['payload']['gcm']['collapse_key']
            if 'delay_while_idle' in message['payload']['gcm']:
                delay_while_idle = message['payload']['gcm']['delay_while_idle']
        # default time to live value is 5 days (in seconds)
        ttl = 432000
        if 'ttl' in message['payload']:
            if 0 < message['payload']['ttl'] < 2419200:
                ttl = message['payload']['ttl']
            else:
                # use default value
                logger.warning('`time_to_live` is out of boundary')
        if 'data' not in message['payload']:
            message['payload']['data'] = {}
        message['payload']['data']['alert'] = message['payload']['alert']
        try:
            response = self.gcm.json_request(registration_ids=message['devices'],
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


if __name__ == '__main__':
    logger.info('starting GCMWorker')
    GCMWorker().start()
