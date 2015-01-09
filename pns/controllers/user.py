# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify
from pns.app import app
from pns.forms import CreateUserForm
from pns.models import db, User


user = Blueprint('user', __name__)


@user.route('/users', methods=['GET'])
def list_users():
    """
    @api {get} /users List Users
    @apiVersion 1.0.0
    @apiName ListUsers
    @apiGroup User

    @apiParam {Number} offset=1
    @apiParam {Number} limit=20

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.users User object array
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
    query = (User
             .query
             .order_by(User.created_at.desc())
             .paginate(page=offset, per_page=limit, error_out=False))
    users = [user_obj.to_dict() for user_obj in query.items]
    return jsonify(success=True, message={'users': users,
                                          'total_pages': query.pages,
                                          'current_page': offset,
                                          'has_next': query.has_next})


@user.route('/users', methods=['POST'])
def add_user():
    """
    @api {post} /users Create User
    @apiVersion 1.0.0
    @apiName CreateUser
    @apiGroup User

    @apiParam {String {..255}} pns_id ID of the user. `pns_id` is a unique identifier for easy third-party integration
        (email, citizen id etc.)

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.user User object

    """
    form = CreateUserForm()
    if not form.validate_on_submit():
        return jsonify(success=False, message=form.errors), 400
    pns_id = request.values.get('pns_id').lower()
    user_obj = User.query.filter_by(pns_id=pns_id).first()
    if user_obj:
        return jsonify(success=True,
                       message={'user': user_obj.to_dict()})
    user_obj = User()
    user_obj.pns_id = pns_id
    db.session.add(user_obj)
    try:
        db.session.commit()
        return jsonify(success=True,
                       message={'user': user_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.exception(ex)
        return jsonify(success=False), 500


@user.route('/users/<pns_id>', methods=['DELETE'])
def delete_user(pns_id):
    """
    @api {delete} /users/:pns_id Delete User
    @apiVersion 1.0.0
    @apiName DeleteUser
    @apiGroup User

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.user User object

    """
    user_obj = User.query.filter_by(pns_id=pns_id).first()
    if not user_obj:
        return jsonify(success=False, message='not found'), 404
    db.session.delete(user_obj)
    try:
        db.session.commit()
        return jsonify(success=True,
                       message={'user': user_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.exception(ex)
        return jsonify(success=False), 500


@user.route('/users/<pns_id>', methods=['GET'])
def get_user(pns_id):
    """
    @api {get} /users/:pns_id Get Unique User
    @apiVersion 1.0.0
    @apiName GetUser
    @apiGroup User

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.user User object

    """
    user_obj = User.query.filter_by(pns_id=pns_id).first()
    if not user_obj:
        return jsonify(success=False, message='not found'), 404
    return jsonify(success=True,
                   message={'user': user_obj.to_dict()})


@user.route('/users/<pns_id>/channels', methods=['GET'])
def get_user_channels(pns_id):
    """
    @api {get} /users/:pns_id/channels List User's Channels
    @apiVersion 1.0.0
    @apiName ListUsersChannels
    @apiGroup User

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.channels Channel object array

    """
    user_obj = User.query.filter_by(pns_id=pns_id).first()
    if not user_obj:
        return jsonify(success=False, message='not found'), 404
    subscriptions = [channel.to_dict() for channel in user_obj.subscriptions.all()]
    return jsonify(success=True,
                   message={'channels': subscriptions})


@user.route('/users/<pns_id>/devices', methods=['GET'])
def get_user_devices(pns_id):
    """
    @api {get} /users/:pns_id/channels List User's Devices
    @apiVersion 1.0.0
    @apiName ListUsersDevices
    @apiGroup User

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.devices Device object array

    """
    user_obj = User.query.filter_by(pns_id=pns_id).first()
    if not user_obj:
        return jsonify(success=False, message='not found'), 404
    devices = [device_obj.to_dict() for device_obj in user_obj.devices.all()]
    return jsonify(success=True, message={'devices': devices})