# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify, request
from pns.app import app
from pns.forms import CreateChannelForm
from pns.models import db, Channel, User, Alert


channel = Blueprint('channel', __name__)


@channel.route('/channels', methods=['POST'])
def create_channel():
    """
    @api {post} /channels Create Channels
    @apiVersion 1.0.0
    @apiName CreateChannel
    @apiGroup Channel

    @apiParam {String {..255}} name Channel name
    @apiParam {String} [description] Channel description

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.channel Channel object

    """
    form = CreateChannelForm()
    if not form.validate_on_submit():
        return jsonify(success=False, message=form.errors), 400
    name = request.values.get('name')
    description = request.values.get('description', None)
    channel_obj = Channel.query.filter_by(name=name).first()
    if channel_obj:
        return jsonify(success=True, message={'channel': channel_obj.to_dict()})
    channel_obj = Channel()
    channel_obj.name = name
    if description:
        channel_obj.description = description
    db.session.add(channel_obj)
    try:
        db.session.commit()
        return jsonify(success=True, message={'channel': channel_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500


@channel.route('/channels', methods=['GET'])
def list_channels():
    """
    @api {get} /channels List Channels
    @apiVersion 1.0.0
    @apiName ListChannels
    @apiGroup Channel

    @apiParam {Number} offset=1
    @apiParam {Number} limit=20

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.channels Channel object array
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
    query = (Channel
             .query
             .order_by(Channel.created_at.desc())
             .paginate(page=offset, per_page=limit, error_out=False))
    channels = [channel_obj.to_dict() for channel_obj in query.items]
    return jsonify(success=True, message={'channels': channels,
                                          'total_pages': query.pages,
                                          'current_page': offset,
                                          'has_next': query.has_next})


@channel.route('/channels/<int:channel_id>', methods=['GET'])
def get_channel(channel_id):
    """
    @api {get} /channels/:channel_id Get Unique Channel
    @apiVersion 1.0.0
    @apiName GetChannel
    @apiGroup Channel

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Array} message.channel Channel object array

    """
    channel_obj = Channel.query.get(channel_id)
    if not channel_obj:
        return jsonify(success=False, message='not found'), 404
    return jsonify(success=True,
                   message={'channel': channel_obj.to_dict()})


@channel.route('/channels/<int:channel_id>', methods=['DELETE'])
def delete_channel(channel_id):
    """
    @api {delete} /channels/:channel_id Delete Channel
    @apiVersion 1.0.0
    @apiName DeleteChannel
    @apiGroup Channel

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.channel Channel object

    """
    channel_obj = Channel.query.get(channel_id)
    if not channel_obj:
        return jsonify(success=False, message='not found'), 404
    db.session.delete(channel_obj)
    try:
        db.session.commit()
        return jsonify(success=True,
                       message={'channel': channel_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500


@channel.route('/channels/<int:channel_id>', methods=['PUT'])
def edit_channel(channel_id):
    """
    @api {put} /channels/:channel_id Update Channel
    @apiVersion 1.0.0
    @apiName UpdateChannel
    @apiGroup Channel

    @apiParam {String {..255}} [name] Channel name
    @apiParam {String} [description] Channel description

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.channel Channel object

    """
    form = CreateChannelForm()
    if not form.validate_on_submit():
        return jsonify(success=False, message=form.errors), 400
    name = request.values.get('name')
    description = request.values.get('description', None)
    channel_obj = Channel.query.get(channel_id)
    if not channel_obj:
        return jsonify(success=False, message='not found'), 404
    channel_obj.name = name
    if description:
        channel_obj.description = description
    db.session.add(channel_obj)
    try:
        db.session.commit()
        return jsonify(success=True, message={'channel': channel_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500


@channel.route('/channels/<int:channel_id>/members', methods=['POST'])
def register_user(channel_id):
    """
    @api {post} /channels/:channel_id/members Subscribe to Channel
    @apiVersion 1.0.0
    @apiName RegisterUserToChannel
    @apiGroup Channel

    @apiHeader {String} Content-Type=application/json Content type must be set to application/json
        and the request body must be raw json

    @apiParam {Array} pns_id Recipients list. Array elements correspond to `pns_id`
    @apiParamExample {json} Request-Example:
        {
            'pns_id': ['alex@example.com', 'neil@example.com']
        }

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.channel Channel object
    @apiSuccess {Object} message.users Users object array

    """
    json_req = request.get_json()
    if not json_req:
        return jsonify(success=False, message='This method requires JSON payload.'), 400
    if ('pns_id' not in json_req or
            ('pns_id' in json_req and not len(json_req['pns_id']))):
        return jsonify(success=False, message={'pns_id': ['This field is required.']})
    if (type(json_req['pns_id']) != list or
            any(map(lambda x: type(x) != unicode, json_req['pns_id']))):
        return jsonify(success=False, message={'pns_id': ['This field requires string array.']})
    pns_id_list = [pns_id.strip() for pns_id in json_req['pns_id']]
    channel_obj = Channel.query.get(channel_id)
    if not channel_obj:
        return jsonify(success=False, message='not found'), 404
    users = User.query.filter(User.pns_id.in_(pns_id_list)).all()
    for user in users:
        channel_obj.subscribers.append(user)
    db.session.add(channel_obj)
    try:
        db.session.commit()
        return jsonify(success=True, message={'channel': channel_obj.to_dict(),
                                              'users': [user.to_dict() for user in users]})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500


@channel.route('/channels/<int:channel_id>/members', methods=['GET'])
def list_channel_members(channel_id):
    """
    @api {get} /channels/:channel_id/members List Channel Members
    @apiVersion 1.0.0
    @apiName GetChannelMembers
    @apiGroup Channel

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
    channel_obj = Channel.query.get(channel_id)
    if not channel_obj:
        return jsonify(success=False, message='not found'), 404
    query = (channel_obj
             .subscribers
             .paginate(page=offset, per_page=limit, error_out=False))
    users = [user.to_dict() for user in query.items]
    return jsonify(success=True, message={'users': users,
                                          'total_pages': query.pages,
                                          'current_page': offset,
                                          'has_next': query.has_next})


@channel.route('/channels/<int:channel_id>/alerts', methods=['GET'])
def list_channel_alerts(channel_id):
    """
    @api {get} /channels/:channel_id/alerts List Channel Alerts
    @apiVersion 1.0.0
    @apiName GetChannelAlerts
    @apiGroup Channel

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
    channel_obj = Channel.query.get(channel_id)
    if not channel_obj:
        return jsonify(success=False, message='not found'), 404
    query = (channel_obj
             .alerts
             .order_by(Alert.created_at.desc())
             .paginate(page=offset, per_page=limit, error_out=False))
    alerts = [alert.to_dict() for alert in query.items]
    return jsonify(success=True, message={'alerts': alerts,
                                          'total_pages': query.pages,
                                          'current_page': offset,
                                          'has_next': query.has_next})


@channel.route('/channels/<int:channel_id>/members/<pns_id>', methods=['DELETE'])
def unregister_user(channel_id, pns_id):
    """
    @api {delete} /channels/:channel_id/members/:pns_id Unsubscribe From Channel
    @apiVersion 1.0.0
    @apiName UnregisterUser
    @apiGroup Channel

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {Object} message.channel Channel object
    @apiSuccess {Object} message.user User object

    """
    user_obj = User.query.filter_by(pns_id=pns_id).first()
    channel_obj = Channel.query.get(channel_id)
    if not user_obj or not channel_obj:
        return jsonify(success=False, message='not found'), 404
    channel_obj.subscribers.remove(user_obj)
    db.session.add(channel_obj)
    try:
        db.session.commit()
        return jsonify(success=True, message={'channel': channel_obj.to_dict(),
                                              'user': user_obj.to_dict()})
    except Exception as ex:
        db.session.rollback()
        app.logger.error(ex)
        return jsonify(success=False), 500