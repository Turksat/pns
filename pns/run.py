# -*- coding: utf-8 -*-

from pns.app import app
from pns.controllers.main import main
from pns.controllers.channel import channel
from pns.controllers.user import user
from pns.controllers.device import device
from pns.controllers.alert import alert


app.register_blueprint(main)
app.register_blueprint(user)
app.register_blueprint(channel)
app.register_blueprint(device)
app.register_blueprint(alert)


if __name__ == '__main__':
    from pns.app import conf
    app.run(host=conf.get('application', 'host'),
            port=conf.getint('application', 'port'))