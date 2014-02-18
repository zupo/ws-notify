# -*- coding: utf-8 -*-
"""Celery tasks."""

from celery import Celery
from celery.task import periodic_task
from datetime import timedelta
from mailer import Mailer
from mailer import Message

import logging
import os
import redis
import requests
import urlparse


# ======
# CONFIG
# ======

VARS = [
    'MAILGUN_SMTP_LOGIN',
    'MAILGUN_SMTP_PASSWORD',
    'MAILGUN_SMTP_PORT',
    'MAILGUN_SMTP_SERVER',
    'REDISTOGO_URL',
]


for var in VARS:
    if not os.environ.get(var):
        raise Exception('Missing env var: {}'.format(var))


# Setup the celery instance under the 'tasks' namespace
app = Celery('tasks')

# Use Redis as our broker and define json as the default serializer
app.conf.update(
    BROKER_URL=os.environ['REDISTOGO_URL'],
    CELERY_TASK_SERIALIZER='json',
    CELERY_ACCEPT_CONTENT=['json', 'msgpack', 'yaml'],
    CELERYD_CONCURRENCY=1,
)


# =====
# UTILS
# =====

def make_srcs_absolute(soup, url):
    for tag in soup.findAll('img'):
        tag['src'] = urlparse.urljoin(url, tag['src'])


# =====
# TASKS
# =====

@periodic_task(run_every=timedelta(seconds=600))
def totisurf():
    response = requests.get('http://totisurf.com')
    assert response.status_code == 200

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text)

    curr_modified = soup.find('font', color='red').text

    db = redis.StrictRedis.from_url(os.environ['REDISTOGO_URL'])
    if not db.get('totisurf_modified'):
        logging.info('Forecast not found in DB, storing modified date to DB.')
        db.set('totisurf_modified', curr_modified)
        return

    old_modified = db.get('totisurf_modified')
    if old_modified != curr_modified:
        logging.info('Forecast was modified, sending email.')
        db.set('totisurf_modified', curr_modified)

        forecast = soup.find(class_='vreme')
        forecast.tr.extract()  # remove the first <tr> "POLAJNAR SVETUJE"
        forecast.find_all('tr')[-1].extract()  # remove the last <tr> "LEGENDA"
        make_srcs_absolute(forecast, url='http://totisurf.com')

        message = Message(
            From=os.environ['MAILGUN_SMTP_LOGIN'],
            To='nejc.zupan@gmail.com',
            Subject="Totisurf forecast changed",
            Html=str(forecast),
        )

        sender = Mailer(
            host=os.environ['MAILGUN_SMTP_SERVER'],
            port=os.environ['MAILGUN_SMTP_PORT'],
            usr=os.environ['MAILGUN_SMTP_LOGIN'],
            pwd=os.environ['MAILGUN_SMTP_PASSWORD'],
            use_tls=True,
        )
        sender.send(message)
    else:
        logging.info('No changes.')
