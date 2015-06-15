# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify
from pns.app import __version__


main = Blueprint('main', __name__)


@main.route('/', methods=['GET'])
def version():
    """
    @api {get} / Get Application Version
    @apiVersion 1.0.0
    @apiName GetVersion
    @apiGroup Version

    @apiSuccess {Boolean} success Request status
    @apiSuccess {Object} message Respond payload
    @apiSuccess {String} message.version Application version

    """
    return jsonify(success=True, message={'version': __version__})
