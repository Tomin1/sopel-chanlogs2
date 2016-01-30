# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

import datetime

from sopel.logger import get_logger


LOGGER = get_logger(__name__)

PRIVMSG_TMPL = '[{time}] <{nick}> {message}'
ACTION_TMPL = '[{time}] * {nick} {message}'
NOTICE_TMPL = '[{time}] -{nick}- {message}'
NICK_TMPL = '[{time}] *** {nick} is now known as {sender}'
JOIN_TMPL = '[{time}] *** Joins: {nick} ({ident}@{host})'
PART_TMPL = '[{time}] *** Parts: {nick} ({ident}@{host}) ({message})'
QUIT_TMPL = '[{time}] *** Quits: {nick} ({ident}@{host}) ({message})'
KICK_TMPL = '[{time}] *** {args[1]} was kicked by {nick} ({message})'
MODE_TMPL = '[{time}] *** {nick} sets mode: {args_str}'
TOPIC_TMPL = '[{time}] *** {nick} changes topic to \'{message}\''


def preformat(bot, trigger, channel):
    now = datetime.datetime.utcnow().replace(microsecond=0)
    if hasattr(trigger, 'time'):
        now = trigger.time.replace(microsecond=0)
    event = {
        'channel':  channel,
        'type':     trigger.event,
        'message':  trigger.match.string,
        'nick':     trigger.nick,
        'ident':    trigger.user,
        'host':     trigger.host,
        'sender':   trigger.sender,
        'datetime': now.isoformat(),
        'date':     now.date().isoformat(),
        'time':     now.time().isoformat(),
        'args':     trigger.args,
        'args_str': ' '.join(trigger.args[1:]),
        'tags':     trigger.tags,
        'intent':   None
    }

    if event['message'].startswith("\001ACTION ") and event['message'].endswith("\001"):
        event['type'] = 'ACTION'
        event['message'] = event['message'][8:-1]

    if 'intent' in trigger.tags:
        event['intent'] = trigger.tags['intent']
    return event


def format(bot, event):
    if 'type' not in event:
        raise ValueError('Event type was unspecified!')

    if getattr(bot.config.chanlogs2, event['type'].lower() + '_template'):
        return getattr(bot.config.chanlogs2, event['type'].lower() + '_template').format(**event)

    if event['type'].upper() + '_TMPL' not in globals():
        LOGGER.warn('No template defined for \'{type}\''.format(event['type'].upper()))

    return globals()[event['type'].upper() + '_TMPL'].format(**event)
