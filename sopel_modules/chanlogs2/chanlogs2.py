# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

import re
import os
import threading
from contextlib import closing

from sopel import module
from sopel.tools import Identifier, SopelMemoryWithDefault
from sopel.config.types import StaticSection, ValidatedAttribute, FilenameAttribute
import psycopg2
from psycopg2.extras import Json


from chanlogs2 import formatter


BAD_CHARS = re.compile(r'[\/?%*:|"<>. ]')


class Chanlogs2Section(StaticSection):
    backend = ValidatedAttribute('backend', default='file')
    privmsg = ValidatedAttribute('privmsg', parse=bool, default=False)

    pg_connection = ValidatedAttribute('pg_connection', default='host=localhost port=5432 dbname=chanlogs')

    # The following config options are only valid if the backend is 'file'
    logdir = FilenameAttribute('logdir', directory=True, default='~/chanlogs')
    by_day = ValidatedAttribute('by_day', parse=bool, default=True)
    allow_toggle = ValidatedAttribute('allow_toggle', parse=bool, default=False)

    privmsg_template = ValidatedAttribute('privmsg_template', default=None)
    action_template = ValidatedAttribute('action_template', default=None)
    notice_template = ValidatedAttribute('notice_template', default=None)
    join_template = ValidatedAttribute('join_template', default=None)
    part_template = ValidatedAttribute('part_template', default=None)
    kick_template = ValidatedAttribute('kick_template', default=None)
    quit_template = ValidatedAttribute('quit_template', default=None)
    nick_template = ValidatedAttribute('nick_template', default=None)
    mode_template = ValidatedAttribute('mode_template', default=None)
    topic_template = ValidatedAttribute('topic_template', default=None)


def configure(config):
    config.define_section('chanlogs2', Chanlogs2Section, validate=False)
    config.chanlogs2.configure_setting('backend', 'Log storage backend (file or postgres)')

    if config.chanlogs2.backend == 'postgres':
        config.chanlogs2.configure_setting('pg_connection', 'PostgreSQL connection string, see http://www.postgresql.org/docs/current/static/libpq-connect.html#LIBPQ-CONNSTRING for more info')
    else:
        config.chanlogs2.configure_setting('logdir', 'Log storage directory')
        config.chanlogs2.configure_setting('allow_toggle', "Start and stop logging on an admin's command")


def setup(bot):
    bot.config.define_section('chanlogs2', Chanlogs2Section)

    if bot.config.chanlogs2.backend == 'postgres':
        connection = get_conn(bot)

        if not connection:
            raise ValueError('Unable to connect with given postgres connection string')

        with closing(connection) as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS chanlogs('
                'id        serial primary key,'
                'network   text,'
                'channel   text,'
                'type      text,'
                'message   text,'
                'nick      text,'
                'ident     text,'
                'host      text,'
                'sender    text,'
                'timestamp timestamp,'
                'args      text[],'
                'tags      json,'
                'intent    text'
                ');'
            )
            conn.commit()
            cursor.close()
    else:
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


@module.rule('.*')
@module.event('TOPIC')
@module.unblockable
def redirect_topic(bot, trigger):
    process_event(bot, trigger)


@module.require_chanmsg('.log is only permitted in channels')
@module.require_admin("Sorry, I can't do that for you")
@module.commands("log")
@module.example('.log start')
def logging_command(bot, trigger):
    if bot.config.chanlogs2.allow_toggle:
        if trigger.group(2) == 'start':
            bot.db.set_channel_value(trigger.sender, 'logging', True)
            bot.reply('Logging started for this channel')
        elif trigger.group(2) == 'stop':
            bot.db.set_channel_value(trigger.sender, 'logging', False)
            bot.reply('Logging stopped for this channel')
        else:
            bot.reply("Please, use '.log start' or '.log stop'")
    else:
        bot.reply("I'm already logging everything.")


def process_event(bot, trigger):
    if trigger.event.upper() in ['QUIT', 'NICK']:
        privcopy = list(bot.privileges.items())
        for channel, privileges in privcopy:
            if trigger.nick in privileges or trigger.sender in privileges:
                event = formatter.preformat(bot, trigger, channel)
                write_log(bot, event, channel)
    else:
        event = formatter.preformat(bot, trigger, trigger.sender)
        write_log(bot, event, trigger.sender)


def write_log(bot, event, channel):
    if bot.config.chanlogs2.allow_toggle:
        if not bot.db.get_channel_value(channel, 'logging'):
            return

    if not isinstance(channel, Identifier):
        channel = Identifier(channel)

    if channel.is_nick() and not bot.config.chanlogs2.privmsg:
        return  # Don't log if we are configured not to log PMs

    if bot.config.chanlogs2.backend == 'postgres':
        write_db_line(bot, event, channel)
    else:
        write_log_line(bot, event, channel)


def get_conn(bot):
    try:
        connection = psycopg2.connect(bot.config.chanlogs2.pg_connection)
        return connection
    except psycopg2.Error as e:
        print(e.pgerror)
        return False


def write_db_line(bot, event, channel):
    connection = get_conn(bot)

    if not connection:
        return

    with closing(connection) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO chanlogs '
            '(network, channel, type, message, nick, ident, host, sender, timestamp, args, tags, intent)'
            ' VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', (bot.config.core.host, 
            event['channel'], event['type'], event['message'], event['nick'], event['ident'], event['host'], 
            event['sender'], event['datetime'], event['args'], Json(event['tags']), event['intent'],))
        conn.commit()
        cursor.close()


def write_log_line(bot, event, channel):
    channel = BAD_CHARS.sub('__', channel)
    channel = Identifier(channel).lower()

    logline = formatter.format(bot, event)

    if bot.config.chanlogs2.by_day:
        filename = "{channel}-{date}.log".format(channel=channel, 
            date=event['date'])
    else:
        filename = "{channel}.log".format(channel=channel)
    logfile = os.path.join(bot.config.chanlogs2.logdir, filename)

    logline = logline + '\n'

    with bot.memory['chanlog2_locks'][logfile]:
        with open(logfile, "ab") as f:
            f.write(logline.encode('utf8'))
