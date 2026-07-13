FROM docker.io/librenms/librenms:26.6.1

LABEL org.opencontainers.image.source="https://github.com/hacwa/k8s-platform"
LABEL org.opencontainers.image.description="LibreNMS with the Keycloak Socialite provider installed"

WORKDIR /opt/librenms

RUN su-exec librenms env \
      HOME=/home/librenms \
      COMPOSER_CACHE_DIR=/tmp/composer-cache \
      ./lnms plugin:add socialiteproviders/keycloak \
    && rm -rf /tmp/composer-cache
