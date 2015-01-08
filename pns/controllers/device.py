# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify
from pns.app import app
from pns.models import db, User, Device
from pns.forms import CreateDeviceForm, UpdateDevice


device = Blueprint('device', __name__)
PLATFORMS = ['gcm', 'apns']


@device.route('/devices/<int:device_id>', methods=['GET'])
def get_device(device_id):
    """
    @api {get} /devices/:device_id Get Unique Device
    @apiVersion 1.0.0
    @apiName GetDevice
    @apiGroup Device

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.device Device object

    """
    device_obj = Device.query.get(device_id)
    if not device_obj:
        return jsonify(success=False, message='not found'), 404
    return jsonify(success=True,
                   message={'device': device_obj.to_dict()})


@device.route('/devices', methods=['GET'])
def list_devices():
    """
    @api {get} /devices List Devices
    @apiVersion 1.0.0
    @apiName ListDevices
    @apiGroup Device

    @apiParam {Number} offset=1
    @apiParam {Number} limit=20

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.devices Device object array
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
    query = (Device
             .query
             .order_by(Device.created_at.desc())
             .paginate(page=offset, per_page=limit, error_out=False))
    devices = [device_obj.to_dict() for device_obj in query.items]
    return jsonify(success=True, message={'devices': devices,
                                          'total_pages': query.pages,
                                          'current_page': offset,
                                          'has_next': query.has_next})


@device.route('/devices', methods=['POST'])
def create_device():
    """
    @api {post} /devices Create Device
    @apiVersion 1.0.0
    @apiName CreateDevice
    @apiGroup Device

    @apiParam {String{..255}} pns_id ID of the user
    @apiParam {String="gcm","apns"} platform Platform of the device
    @apiParam {String} platform_id Platform token of the device

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.device Device object

    """
    form = CreateDeviceForm()
    if form.validate_on_submit():
        pns_id = request.values.get('pns_id')
        platform = request.values.get('platform', '').lower()
        platform_id = request.values.get('platform_id')
        if platform not in PLATFORMS:
            return jsonify(success=False, message='unknown platform'), 400
        user_obj = User.query.filter_by(pns_id=pns_id).first()
        if not user_obj:
            return jsonify(success=False, message='not found'), 404
        device_obj = Device()
        device_obj.platform = platform
        device_obj.platform_id = platform_id
        device_obj.user = user_obj
        db.session.add(device_obj)
        try:
            db.session.commit()
            return jsonify(success=True,
                           message={'device': device_obj.to_dict()})
        except Exception as ex:
            db.session.rollback()
            app.logger.error(ex)
            return jsonify(success=False), 500
    else:
        return jsonify(success=False, message=form.errors), 400


@device.route('/devices/<int:device_id>', methods=['DELETE'])
def delete_device(device_id):
    """
    @api {delete} /devices/:device_id Delete Device
    @apiVersion 1.0.0
    @apiName DeleteDevice
    @apiGroup Device

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.device Device object

    """
    device_obj = Device.query.get(device_id)
    if not device_obj:
        return jsonify(success=False, message='not found'), 404
    db.session.delete(device_obj)
    try:
        db.session.commit()
        return jsonify(success=True,
                       message={'device': device_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500


@device.route('/devices/<int:device_id>', methods=['PUT'])
def mute_device(device_id):
    """
    @api {put} /devices/:device_id Mute Alerts for Specific Device
    @apiVersion 1.0.0
    @apiName MuteDevice
    @apiGroup Device

    @apiParam {Boolean} mute=false Mute alerts for future notifications. Don't set for a 'false' value.

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.device Device object

    """
    form = UpdateDevice()
    if not form.validate_on_submit():
        return jsonify(success=False, message=form.errors), 400
    device_obj = Device.query.get(device_id)
    if not device_obj:
        return jsonify(success=False, message='not found'), 404
    device_obj.mute = form.mute.data
    db.session.add(device_obj)
    try:
        db.session.commit()
        return jsonify(success=True,
                       message={'device': device_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500