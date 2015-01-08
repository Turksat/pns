# -*- coding: utf-8 -*-

import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from pns.app import db


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
                         db.Column('user_id', db.Integer,
                                   db.ForeignKey('user.id')),
                         db.Column('channel_id', db.Integer,
                                   db.ForeignKey('channel.id')),
                         UniqueConstraint('user_id', 'channel_id'))


class User(db.Model, SerializationMixin):
    """user resource
    """
    id = db.Column(db.Integer, primary_key=True)
    # pns_id is a unique identifier for easy third-party integration (email, citizen id etc.)
    pns_id = db.Column(db.String(255), unique=True, nullable=False)
    subscriptions = db.relationship('Channel',
                                    secondary=subscriptions,
                                    lazy='dynamic',
                                    backref=db.backref('subscribers',
                                                       lazy='dynamic'))
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
    alerts = db.relationship('Alert', backref='channel', lazy='dynamic',
                                    cascade='all, delete, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                        index=True, nullable=False)
    platform = db.Column(db.String(10), index=True, nullable=False)
    platform_id = db.Column(db.Text, unique=True, nullable=False)
    mute = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)

    def __repr__(self):
        return '<Device %r>' % self.id


if __name__ == '__main__':
    db.create_all()