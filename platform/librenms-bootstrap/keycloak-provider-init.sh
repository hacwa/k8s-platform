#!/bin/sh
set -eu

cd /opt/librenms

echo "Installing LibreNMS Keycloak Socialite provider..."

FORCE=1 gosu librenms composer require \
  socialiteproviders/keycloak:5.3.0 \
  --no-interaction \
  --no-progress

gosu librenms php artisan config:clear

echo "LibreNMS Keycloak Socialite provider installed."
