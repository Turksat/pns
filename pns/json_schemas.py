# -*- coding: utf-8 -*-

from schema import Schema, And, Optional

# validate structure of JSON request for `alert` creation
alert_schema = Schema({
    "alert": And(unicode, len),
    Optional("channel_id"): And(int, lambda x: x > 0),
    Optional("pns_id"): [unicode],
    Optional("ttl"): And(int, lambda x: x > 0),
    Optional("appid"): And(unicode, len),
    Optional("appver"): And(int, lambda x: x > 0),
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

# validate structure of JSON request for `user` registration to a `channel`
registration_schema = Schema({"pns_id": [unicode]})
