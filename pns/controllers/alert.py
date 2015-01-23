# -*- coding: utf-8 -*-

import pika
from pika.exceptions import ConnectionClosed
from flask import Blueprint, request, jsonify
from flask.json import dumps
from schema import Schema, And, Optional
from pns.app import app, conf
from pns.models import db, Alert


alert = Blueprint('alert', __name__)

# validate structure of JSON request for `alert` creation
alert_schema = Schema({
    "alert": And(unicode, len),
    Optional("channel_id"): And(int, lambda x: x > 0),
    Optional("pns_id"): [unicode],
    Optional("ttl"): And(int, lambda x: x > 0),
    Optional("gcm"): {
        Optional("delay_while_idle"): bool,
        Optional("collapse_key"): And(unicode, len)
    },
    Optional("apns"): {
        Optional("sound"): And(unicode, len),
        Optional("badge"): And(int, lambda x: x >= 0),
        Optional("content_available"): And(int, lambda x: x in [0, 1])
    },
    Optional("data"): dict
})


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
        except Exception as ex:
            app.logger.exception(ex)

    def basic_publish(self, *args, **kwargs):
        try:
            return self.channel.basic_publish(*args, **kwargs)
        except ConnectionClosed:
            self._disconnect()
            self._connect()
            return self.channel.basic_publish(*args, **kwargs)


conn_manager = PikaConnectionManager(username=conf.get('rabbitmq', 'username'),
                                     password=conf.get('rabbitmq', 'password'),
                                     host=conf.get('rabbitmq', 'host'),
                                     heartbeat_interval=conf.getint('rabbitmq', 'server_heartbeat_interval'))
conn_manager.channel.exchange_declare(exchange='pns_exchange', type='direct', durable=True)


@alert.route('/alerts', methods=['POST'])
def notify():
    """
    @api {post} /alerts Create Alert
    @apiVersion 1.0.0
    @apiName CreateAlert
    @apiGroup Alert

    @apiParam {String} alert Alert message
    @apiParam {Number} [channel_id] ID of the channel. Both `channel_id` and `pns_id` fields are optional but at least one of
        them must be provided
    @apiParam {Array} [pns_id] Recipients list. Array elements correspond to `pns_id`
    @apiParam {Number} [ttl='platform specific defaults'] Time to live (in seconds)

    @apiParam {Object} [gcm] GCM specific parameters
    @apiParam {Boolean} [gcm.delay_while_idle=false] This parameter indicates that the message
        should not be sent immediately if the device is idle.
    @apiParam {String} [gcm.collapse_key] This parameter specifies an arbitrary string (such as "Updates Available")
        that is used to collapse a group of like messages when the device is offline, so that only the last message gets sent to the client.

    @apiParam {Object} [apns] APNS specific parameters
    @apiParam {String} [apns.sound=default] The name of a sound file in the app bundle
    @apiParam {Number} [apns.badge] The number to display as the badge of the app icon
    @apiParam {Number=0,1} [apns.content_available=0] Provide this key with a value of 1 to indicate that new content is available

    @apiParam {Object} [data] Arbitrary key-value object

    @apiParamExample {json} Request-Example:
        {
            'alert': 'some important message here',
            'channel_id': 12,
            'pns_id': ['alex@example.com', 'neil@example.com'],
            'gcm': {
                'delay_while_idle': true,
                'collapse_key': 'new_version',
            },
            'apns': {
                'content_available': 1,
            }
            'data': {
                'url': 'http://example.com/'
            }
        }

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.alert Alert object

    """
    json_req = request.get_json(force=True)
    try:
        alert_schema.validate(json_req)
    except Exception as ex:
        return jsonify(success=False, message={'error': str(ex)}), 400
    alert_obj = Alert()
    if 'channel_id' in json_req:
        alert_obj.channel_id = json_req['channel_id']
    alert_obj.payload = json_req
    db.session.add(alert_obj)
    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        app.logger.exception(ex)
        return jsonify(success=False), 500
    try:
        if conn_manager.basic_publish(exchange='pns_exchange',
                                      routing_key='pns_pre_processing',
                                      body=dumps(alert_obj.to_dict(), ensure_ascii=False),
                                      mandatory=True,
                                      properties=pika.BasicProperties(
                                          delivery_mode=2,  # make message persistent
                                          content_type='application/json')):
            return jsonify(success=True, message={'alert': alert_obj.to_dict()})
        else:
            app.logger.error('failed to deliver message to rabbitmq server: %r' % alert_obj)
            return jsonify(success=False), 500
    except Exception as ex:
        app.logger.exception(ex)
        return jsonify(success=False), 500



@alert.route('/alerts', methods=['GET'])
def list_alerts():
    """
    @api {get} /alerts List Alerts
    @apiVersion 1.0.0
    @apiName ListAlerts
    @apiGroup Alert

    @apiParam {Number} offset=1
    @apiParam {Number} limit=20

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.alerts Alert object array
    @apiSuccess {Number} message.total_pages Total number of available pages
    @apiSuccess {Number} message.current_page Current page number
    @apiSuccess {Boolean} message.has_next Next page available flag

    """
    try:
        offset = int(request.values.get('offset', 1))
        limit = int(request.values.get('limit', 20))
    except ValueError:
        offset = 1
        limit = 20
    query = (Alert
             .query
             .order_by(Alert.created_at.desc())
             .paginate(page=offset, per_page=limit, error_out=False))
    alerts = [alert_obj.to_dict() for alert_obj in query.items]
    return jsonify(success=True, message={'alerts': alerts,
                                          'total_pages': query.pages,
                                          'current_page': offset,
                                          'has_next': query.has_next})