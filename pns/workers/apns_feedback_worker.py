# -*- coding: utf-8 -*-

import logging
from apns_clerk import APNs, Session
from pns.utils import get_conf, get_logging_handler
from pns.models import db, Device


conf = get_conf()

# configure logger
logging.captureWarnings(True)
logger = logging.getLogger(__name__)
logger.addHandler(get_logging_handler())
if conf.getboolean('application', 'debug'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)


class APNSFeedbackWorker(object):
    def __init__(self):
        # apns configuration
        session = Session()
        if conf.getboolean('application', 'debug'):
            con = session.new_connection("feedback_sandbox", cert_file=conf.get('apns', 'cert_sandbox'))
        else:
            con = session.new_connection("feedback_production", cert_file=conf.get('apns', 'cert_production'))
        self.srv = APNs(con)

    def start(self):
        try:
            # on any IO failure after successful connection this generator
            # will simply stop iterating. you will pick the rest of the tokens
            # during next feedback session.
            for token, when in self.srv.feedback():
                # every time a devices sends you a token, you should store
                # {token: given_token, last_update: datetime.datetime.now()}
                device = Device.query.filter_by(platform_id=token).first()
                if not device:
                    continue
                if device.updated_at and device.updated_at < when:
                    # the token wasn't updated after the failure has
                    # been reported, so the token is invalid and you should
                    # stop sending messages to it.
                    db.session.delete(device)
                elif not device.updated_at:
                    db.session.delete(device)
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            logger.exception(ex)


if __name__ == '__main__':
    logger.info('starting APNSFeedbackWorker')
    APNSFeedbackWorker().start()
