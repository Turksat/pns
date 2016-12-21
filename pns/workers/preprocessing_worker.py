# -*- coding: utf-8 -*-

import logging
import pika
from sqlalchemy.sql.expression import false
from flask.json import loads, dumps
from pns.utils import get_conf, get_logging_handler, PikaConnectionManager
from pns.models import db, User, Device, Channel


conf = get_conf()

# configure logger
logging.captureWarnings(True)
logger = logging.getLogger(__name__)
logger.addHandler(get_logging_handler())
if conf.getboolean('application', 'debug'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

class PreProcessingWorker(object):
    def __init__(self):
        self.GCM = "gcm"
        self.APNS = "apns"
        self.chunk_size = 1000
        # rabbitmq configuration
        self.cm = PikaConnectionManager(username=conf.get('rabbitmq', 'username'),
                                        password=conf.get('rabbitmq', 'password'),
                                        host=conf.get('rabbitmq', 'host'),
                                        heartbeat_interval=conf.getint('rabbitmq', 'worker_heartbeat_interval'))
        self.cm.channel.exchange_declare(exchange='pns_exchange', type='direct', durable=True)
        self.cm.channel.exchange_declare(exchange='pns_exchange', type='direct', durable=True)
        self.cm.channel.queue_declare(queue='pns_pre_processing_queue', durable=True)
        self.cm.channel.queue_bind(exchange='pns_exchange', queue='pns_pre_processing_queue',
                                   routing_key='pns_pre_processing')
        self.cm.channel.basic_qos(prefetch_count=1)
        self.cm.channel.basic_consume(self._callback, queue='pns_pre_processing_queue')
        self.rowcountpaa = 0

    def start(self):
        self.cm.channel.start_consuming()

    def _callback(self, ch, method, properties, body):
        """
        get device list and divide chunks according to platform type (APNS and GCM)
        GCM broadcasting calls allow only 1000 recipients at one time. Follow same size for APNS work load.
        :param ch:
        :param method:
        :param properties:
        :param body:
        :return:
        """
        message = loads(body)
        logger.debug('message: %s' % message)
        mobile_app_id = None
        mobile_app_ver = None
        pns_id_list = None
        channel_id = None
        if 'appid' in message['payload']:
            mobile_app_id = message['payload']['appid']
        if 'appver' in message['payload']:
            mobile_app_ver = message['payload']['appver']
        if 'pns_id' in message['payload'] and len(message['payload']['pns_id']):
            pns_id_list = message['payload']['pns_id']
        if 'channel_id' in message and message['channel_id']:
            channel_id = message['channel_id']
        if pns_id_list:
            # filter by pns_id
            if conf.getboolean('apns', 'enabled'):
                for devices in self.get_user_devices(pns_id_list, self.APNS, mobile_app_id, mobile_app_ver):
                    self.publish_apns(devices, message['payload'])
            if conf.getboolean('gcm', 'enabled'):
                for devices in self.get_user_devices(pns_id_list, self.GCM, mobile_app_id, mobile_app_ver):
                    self.publish_gcm(devices, message['payload'])
        if channel_id:
            # filter by channel_id
            if conf.getboolean('apns', 'enabled'):
                for devices in self.get_channel_devices(channel_id, self.APNS, mobile_app_id, mobile_app_ver):
                    self.publish_apns(devices, message['payload'])
            if conf.getboolean('gcm', 'enabled'):
                for devices in self.get_channel_devices(channel_id, self.GCM, mobile_app_id, mobile_app_ver):
                    self.publish_gcm(devices, message['payload'])
        if not pns_id_list and not channel_id and mobile_app_id and mobile_app_ver:
            # filter by application id and min application version number
            if conf.getboolean('apns', 'enabled'):
                for devices in self.get_by_app_ver(self.APNS, mobile_app_id, mobile_app_ver):
                    self.publish_apns(devices, message['payload'])
            if conf.getboolean('gcm', 'enabled'):
                for devices in self.get_by_app_ver(self.GCM, mobile_app_id, mobile_app_ver):
                    self.publish_gcm(devices, message['payload'])
        self.rowcountpaa = 0
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def get_user_devices(self, pns_id_list, platform, mobile_app_id, mobile_app_ver):
        """
        Yield registered devices of users
        :param pns_id_list:
        :param platform:
        :return:
        """
        device_list = []
        device_list_query = (db
                             .session
                             .query(Device.platform_id)
                             .join(User)
                             .filter(User.pns_id.in_(pns_id_list))
                             .filter(Device.platform == platform)
                             .filter(Device.mute == false()))
        if mobile_app_id and mobile_app_ver:
            device_list_query = (device_list_query
                                 .filter(Device.mobile_app_id == mobile_app_id)
                                 .filter(Device.mobile_app_ver >= mobile_app_ver))
        for device in device_list_query.yield_per(self.chunk_size):
            device_list.append(device[0])
            if len(device_list) % self.chunk_size == 0:
                yield device_list
                device_list = []
        if len(device_list) % self.chunk_size > 0:
            yield device_list

    def get_channel_devices(self, channel_id, platform, mobile_app_id, mobile_app_ver):
        """
        Yield registered devices of channel
        :param channel_id:
        :param platform:
        :return:
        """
        device_list = []
        device_list_query = (Channel
                             .query
                             .get(channel_id)
                             .devices
                             .filter(Device.platform == platform)
                             .filter(Device.mute == false()))
        if mobile_app_id and mobile_app_ver:
            device_list_query = (device_list_query
                                 .filter(Device.mobile_app_id == mobile_app_id)
                                 .filter(Device.mobile_app_ver >= mobile_app_ver))
        for device in device_list_query.with_entities(Device.platform_id).yield_per(self.chunk_size):
            device_list.append(device[0])
            if len(device_list) % self.chunk_size == 0:
                yield device_list
                device_list = []
        if len(device_list) % self.chunk_size > 0:
            yield device_list

    def get_by_app_ver(self, platform, mobile_app_id, mobile_app_ver):
        """
        Yield registered devices by filtering application id and min version number
        :param platform:
        :param mobile_app_id:
        :param mobile_app_ver:
        :return:
        """
        device_list = []
        device_list_query = self.get_by_app_ver_query(platform, mobile_app_id, mobile_app_ver)
        if self.rowcountpaa == 0:
            self.rowcountpaa = self.get_by_app_ver_query(platform, mobile_app_id, mobile_app_ver).count()
        i = 0
        for device in device_list_query.yield_per(self.chunk_size):
            device_list.append(device[0])
            i += 1
            if len(device_list) % self.chunk_size == 0:
                logger.info(str(i) + "..." + str(self.rowcountpaa) + " " +platform + " ...Send to rabbitmq")
                yield device_list
                device_list = []
        if len(device_list) % self.chunk_size > 0:
            logger.info(str(i) + "..." + str(self.rowcountpaa) + " " +platform + " ...Send to rabbitmq")
            yield device_list

    def get_by_app_ver_query(self, platform, mobile_app_id, mobile_app_ver):
        return (db
         .session
         .query(Device.platform_id)
         .join(User)
         .filter(Device.platform == platform)
         .filter(Device.mute == false())
         .filter(Device.mobile_app_id == mobile_app_id)
         .filter(Device.mobile_app_ver >= mobile_app_ver))

    def publish_gcm(self, gcm_devices, payload):
        """
        publish gcm token list and message payload to gcm worker
        :param gcm_devices:
        :param payload:
        :return:
        """
        self.cm.basic_publish(exchange='pns_exchange',
                              routing_key='pns_gcm',
                              body=dumps({'devices': gcm_devices, 'payload': payload}, ensure_ascii=False),
                              mandatory=True,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                                  content_type='application/json'))

    def publish_apns(self, apns_devices, payload):
        """
        publish apns token list and message payload to apns worker
        :param apns_devices:
        :param payload:
        :return:
        """
        self.cm.basic_publish(exchange='pns_exchange',
                              routing_key='pns_apns',
                              body=dumps({'devices': apns_devices, 'payload': payload}, ensure_ascii=False),
                              mandatory=True,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                                  content_type='application/json'))


if __name__ == '__main__':
    logger.info('starting PreProcessingWorker')
    PreProcessingWorker().start()
