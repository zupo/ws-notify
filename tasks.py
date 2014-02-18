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
    'REDISCLOUD_URL',
]


for var in VARS:
    if not os.environ.get(var):
        raise Exception('Missing env var: {}'.format(var))


# Setup the celery instance under the 'tasks' namespace
app = Celery('tasks')

# Use Redis as our broker and define json as the default serializer
app.conf.update(
    BROKER_URL=os.environ['REDISCLOUD_URL'],
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

    db = redis.StrictRedis.from_url(os.environ['REDISCLOUD_URL'])
    if not db.get('totisurf_modified'):
        logging.info('totisurf_modified not found in DB, storing "{}".'.format(
            curr_modified))
        db.set('totisurf_modified', curr_modified)
        return

    old_modified = db.get('totisurf_modified')
    if old_modified != curr_modified:
        logging.info(
            'totisurf_modified modified, sending email, storing "{}".'.format(
                curr_modified))

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


@periodic_task(run_every=timedelta(seconds=600))
def waveriderz():
    response = requests.get('http://waveriderz.wordpress.com/')
    assert response.status_code == 200

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text)

    curr_forecast = soup.find('div', class_='textwidget').text

    db = redis.StrictRedis.from_url(os.environ['REDISCLOUD_URL'])
    if not db.get('waveriderz_forecast'):
        logging.info('waveriderz_forecast not found in DB, storing "{}".'.format(  # noqa
            curr_forecast))
        db.set('waveriderz_forecast', curr_forecast)
        return

    old_forecast = db.get('waveriderz_forecast')
    if old_forecast != curr_forecast:
        logging.info(
            'waveriderz_forecast modified, sending email, storing "{}".'.format(  # noqa
                curr_forecast))
        db.set('waveriderz_forecast', curr_forecast)

        message = Message(
            From=os.environ['MAILGUN_SMTP_LOGIN'],
            To='nejc.zupan@gmail.com',
            Subject="Waveriderz forecast changed",
            Html=u'Borut pravi: <br />' + curr_forecast,
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
