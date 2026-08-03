#!/bin/sh
set -eu

CONF="${MPD_CONF:-/etc/mpd.conf}"

if [ -f /config/mpd.conf ]; then
  CONF=/config/mpd.conf
fi

mkdir -p /music /var/lib/mpd/playlists /run/mpd
chown -R mpd:audio /music /var/lib/mpd /run/mpd
chmod -R a+rwX /music

exec su -s /bin/sh mpd -c "mpd --no-daemon --stdout '$CONF'"
