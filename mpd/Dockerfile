FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends mpd mpc \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /music /var/lib/mpd/playlists /run/mpd /config \
    && chown -R mpd:audio /music /var/lib/mpd /run/mpd /config

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 6600 8000

# Start as root so entrypoint can fix /music permissions on named volumes,
# then drop privileges via setpriv / su-exec pattern.
USER root
ENTRYPOINT ["/entrypoint.sh"]
