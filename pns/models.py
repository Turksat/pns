# -*- coding: utf-8 -*-

import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from pns.app import app, db


class SerializationMixin():
    """serialization mixin for sqlalchemy model object
    """
    def to_dict(self, *exceptions, **extra_payload):
        """get dict representation of the object
        :param list exceptions: a list to discard from dict
        :param dict extra_payload: new parameters to add to dict
        """
        _dict = ({c.name: getattr(self, c.name) for c in self.__table__.columns
                 if c.name not in exceptions})
        _dict.update(**extra_payload)
        return _dict


subscriptions = db.Table('subscriptions',
                         db.Column('user_id', db.Integer, db.ForeignKey('user.id'), nullable=False),
                         db.Column('channel_id', db.Integer, db.ForeignKey('channel.id'), nullable=False),
                         UniqueConstraint('user_id', 'channel_id'))


channel_devices = db.Table('channel_devices',
                           db.Column('channel_id', db.Integer, db.ForeignKey('channel.id'), nullable=False),
                           db.Column('device_id', db.Integer, db.ForeignKey('device.id'), nullable=False),
                           UniqueConstraint('channel_id', 'device_id'))


class User(db.Model, SerializationMixin):
    """user resource
    """
    id = db.Column(db.Integer, primary_key=True)
    # pns_id is a unique identifier for easy third-party integration (email, citizen id etc.)
    pns_id = db.Column(db.String(255), unique=True, nullable=False)
    subscriptions = db.relationship('Channel',
                                    secondary=subscriptions,
                                    lazy='dynamic',
                                    backref=db.backref('subscribers', lazy='dynamic'))
    devices = db.relationship('Device', backref='user', lazy='dynamic',
                              cascade='all, delete, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)

    def __repr__(self):
        return '<User %r>' % self.id


class Channel(db.Model, SerializationMixin):
    """channel resource
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    devices = db.relationship('Device',
                              secondary=channel_devices,
                              lazy='dynamic',
                              backref=db.backref('channels', lazy='dynamic'))
    alerts = db.relationship('Alert', backref='channel', lazy='dynamic',
                             cascade='all, delete, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)

    def subscribe_user(self, user):
        try:
            self.subscribers.append(user)
            for device in user.devices.all():
                self.devices.append(device)
            db.session.add(self)
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            app.logger.exception(ex)
            return False
        return True

    def unsubscribe_user(self, user):
        try:
            self.subscribers.remove(user)
            for device in user.devices.all():
                self.devices.remove(device)
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            app.logger.exception(ex)
            return False
        return True

    def __repr__(self):
        return '<Channel %r>' % self.id


class Alert(db.Model, SerializationMixin):
    """alert resource
    """
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), index=True)
    payload = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)

    def __repr__(self):
        return '<Alert %r>' % self.id


class Device(db.Model, SerializationMixin):
    """device resource
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True, nullable=False)
    platform = db.Column(db.String(10), index=True, nullable=False)
    platform_id = db.Column(db.Text, unique=True, nullable=False)
    mute = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)

    def subscribe_to_channels(self):
        """subscribe new device to existing channels
        """
        try:
            for channel in self.user.subscriptions.all():
                channel.devices.append(self)
            db.session.add(self.user)
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            app.logger.exception(ex)
            return False
        return True

    def __repr__(self):
        return '<Device %r>' % self.id


if __name__ == '__main__':
    db.create_all()