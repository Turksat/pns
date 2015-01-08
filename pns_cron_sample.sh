#!/bin/sh
# Check APNS errors

export PYTHONPATH=$PYTHONPATH:/home/user/pns/
export PNSCONF="/home/user/config.ini"

/home/user/env/bin/python /home/user/pns/workers/apns_feedback_worker.py