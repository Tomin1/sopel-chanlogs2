Sopel-Chanlogs2
===============

Quick rewrite of the old sopel chanlogs module to fix some bugs and
clean up the code.

Configuration
~~~~~~~~~~~~

::

    [chanlogs2]
    logdir = ~/chanlogs
    by_day = True
    privmsg = False

By default all events are formatted using Energymech format to match
with ZNC logs. You can easily change these formats by specifying
``<event>_template`` in the config. For example:
``privmsg_template = [{time}] <{nick}> {message}``

Supported Tokens
~~~~~~~~~~~~~~~

::

    {channel} - Channel which the message was sent it, will be a nick if message is a PM
    {type} - Type of message (PRIVMSG, QUIT, JOIN, etc...)
    {message} - Message itself
    {nick} - Nick of sender
    {ident} - Ident of sender
    {host} - hostname of sender
    {sender} - alias for channel
    {datetime} - datetime ISO formatted
    {date} - date ISO formatted
    {time} - time ISO formatted
    {args} - list of raw message args
    {args_str} - stringified version of args
    {tags} - list of IRCv3 tags
    {intent} - IRCv3 intent
