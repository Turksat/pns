# -*- coding: utf-8 -*-

from flask_wtf import Form
from wtforms.fields import StringField, BooleanField
from wtforms.validators import DataRequired, Length, Optional


class CreateUserForm(Form):
    pns_id = StringField('pns_id', validators=[DataRequired()])


class CreateDeviceForm(Form):
    pns_id = StringField('pns_id', validators=[DataRequired()])
    platform = StringField('platform', validators=[DataRequired()])
    platform_id = StringField('platform_id', validators=[DataRequired()])


class CreateChannelForm(Form):
    name = StringField('name', validators=[DataRequired(), Length(max=255)])
    description = StringField('description', validators=[Optional()])


class UpdateDevice(Form):
    mute = BooleanField('mute', default=False)