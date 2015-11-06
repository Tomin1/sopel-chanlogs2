# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

import datetime
import re
import os
import threading

from sopel import module
from sopel.tools import Identifier, SopelMemoryWithDefault
from sopel.config.types import StaticSection, ValidatedAttribute

from chanlogs2 import formatter


BAD_CHARS = re.compile(r'[\/?%*:|"<>. ]')


class Chanlogs2Section(StaticSection):
    logdir = ValidatedAttribute('logdir', default='~/chanlogs')
    by_day = ValidatedAttribute('by_day', parse=bool, default=True)
    privmsg = ValidatedAttribute('privmsg', parse=bool, default=False)

    privmsg_template = ValidatedAttribute('privmsg_template', default=None)
    action_template = ValidatedAttribute('action_template', default=None)
    notice_template = ValidatedAttribute('notice_template', default=None)
    join_template = ValidatedAttribute('join_template', default=None)
    part_template = ValidatedAttribute('part_template', default=None)
    kick_template = ValidatedAttribute('kick_template', default=None)
    quit_template = ValidatedAttribute('quit_template', default=None)
    nick_template = ValidatedAttribute('nick_template', default=None)
    mode_template = ValidatedAttribute('mode_template', default=None)


def configure(config):
    config.define_section('chanlogs2', Chanlogs2Section, validate=False)
    config.chanlogs2.configure_setting('logdir', 'Log storage directory')


def setup(bot):
    bot.config.define_section('chanlogs2', Chanlogs2Section)

    basedir = os.path.expanduser(bot.config.chanlogs2.logdir)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
    bot.config.chanlogs2.logdir = basedir

    # locks for log files
    if not bot.memory.contains('chanlog2_locks'):
        bot.memory['chanlog2_locks'] = SopelMemoryWithDefault(threading.Lock)


@module.rule('.*')
@module.unblockable
def redirect_msg(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('NOTICE')
@module.unblockable
def redirect_notice(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('JOIN')
@module.unblockable
def redirect_join(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('PART')
@module.unblockable
def redirect_part(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('KICK')
@module.unblockable
def redirect_kick(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('NICK')
@module.unblockable
def redirect_nick(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('QUIT')
@module.priority('high')
@module.unblockable
def redirect_quit(bot, trigger):
    process_event(bot, trigger)


@module.rule('.*')
@module.event('MODE')
@module.unblockable
def redirect_mode(bot, trigger):
    process_event(bot, trigger)


def process_event(bot, trigger):
    if trigger.event.upper() in ['QUIT', 'NICK']:
        privcopy = list(bot.privileges.items())
        for channel, privileges in privcopy:
            if trigger.nick in privileges or trigger.sender in privileges:
                event = formatter.preformat(bot, trigger, channel)
                write_log_line(bot, formatter.format(bot, event), channel)
    else:
        event = formatter.preformat(bot, trigger, trigger.sender)
        write_log_line(bot, formatter.format(bot, event), trigger.sender)


def write_log_line(bot, logline, channel):
    if not isinstance(channel, Identifier):
        channel = Identifier(channel)

    if channel.is_nick() and not bot.config.chanlogs2.privmsg:
        return # Don't log if we are configured not to log PMs

    channel = BAD_CHARS.sub('__', channel)
    channel = Identifier(channel).lower()

    if bot.config.chanlogs2.by_day:
        filename = "{channel}-{date}.log".format(channel=channel, 
            date=datetime.datetime.utcnow().date().isoformat())
    else:
        filename = "{channel}.log".format(channel=channel)
    logfile = os.path.join(bot.config.chanlogs2.logdir, filename)

    logline = logline + '\n'

    with bot.memory['chanlog2_locks'][logfile]:
        with open(logfile, "ab") as f:
            f.write(logline.encode('utf8'))
