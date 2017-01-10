# -*- coding: utf-8 -*-

import pika
from flask import Blueprint, request, jsonify
from flask.json import dumps
from pns.utils import PikaConnectionManager
from pns.app import app, conf
from pns.models import db, Alert
from pns.json_schemas import alert_schema


alert = Blueprint('alert', __name__)

conn_manager = PikaConnectionManager(username=conf.get('rabbitmq', 'username'),
                                     password=conf.get('rabbitmq', 'password'),
                                     host=conf.get('rabbitmq', 'host'),
                                     heartbeat_interval=conf.getint('rabbitmq', 'server_heartbeat_interval'))
conn_manager.channel.exchange_declare(exchange='pns_exchange', type='direct', durable=True)


@alert.route('/alerts', methods=['POST'])
def notify():
    """
    @api {post} /alerts Create Alert
    @apiVersion 3.3.0
    @apiName CreateAlert
    @apiGroup Alert

    @apiParam {String} alert Alert message
    @apiParam {Number} [channel_id] ID of the channel. Both `channel_id` and `pns_id` fields are optional but at least one of
        them must be provided
    @apiParam {Array} [pns_id] Recipients list. Array elements correspond to `pns_id`
    @apiParam {String} [appid] Package name of mobile application to send alerts
    @apiParam {Number} [appver] Minimum version of mobile application to send alerts (minimum version number will be included)
    @apiParam {Number} [ttl='432000 (5 days)'] Time to live (in seconds)

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
            "alert": "some important message here",
            "channel_id": 12,
            "pns_id": ["alex@example.com", "neil@example.com"],
            "appid": "com.example.mypackage",
            "appver": 1200,
            "gcm": {
                "delay_while_idle": true,
                "collapse_key": "new_version"
            },
            "apns": {
                "content_available": 1
            },
            "data": {
                "url": "http://example.com/"
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
    if conf.getboolean('application', 'save_alerts'):
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
