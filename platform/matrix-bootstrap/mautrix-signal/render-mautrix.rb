#!/usr/bin/env ruby

require "cgi"
require "fileutils"
require "yaml"

if ARGV.length != 4
  abort(
    "usage: render-mautrix.rb CONFIG_TEMPLATE " \
    "REGISTRATION_TEMPLATE OUTPUT_DIRECTORY SECRET_DIRECTORY"
  )
end

config_template = ARGV[0]
registration_template = ARGV[1]
output_directory = ARGV[2]
secret_directory = ARGV[3]

def read_secret(directory, filename)
  value = File.read(
    File.join(directory, filename)
  ).sub(/\n\z/, "")

  abort("#{filename} is empty") if value.empty?

  value
end

def ensure_hash_path(document, path)
  current = document

  path.each do |key|
    unless current[key].is_a?(Hash)
      abort("Missing configuration path: #{path.join('.')}")
    end

    current = current[key]
  end

  current
end

config = YAML.safe_load(
  File.read(config_template),
  permitted_classes: [],
  permitted_symbols: [],
  aliases: true,
)

registration = YAML.safe_load(
  File.read(registration_template),
  permitted_classes: [],
  permitted_symbols: [],
  aliases: true,
)

database = ensure_hash_path(
  config,
  ["database"],
)

homeserver = ensure_hash_path(
  config,
  ["homeserver"],
)

appservice = ensure_hash_path(
  config,
  ["appservice"],
)

database_password = read_secret(
  secret_directory,
  "database-password",
)

encoded_password = CGI.escape(
  database_password
).gsub("+", "%20")

database["uri"] = (
  "postgres://mautrix_signal:" \
  "#{encoded_password}@" \
  "synapse-postgresql:5432/mautrix_signal" \
  "?sslmode=disable"
)

homeserver["address"] = "http://synapse:8008"
appservice["address"] = "http://mautrix-signal:29328"

appservice["as_token"] = read_secret(
  secret_directory,
  "as-token",
)

appservice["hs_token"] = read_secret(
  secret_directory,
  "hs-token",
)

registration["as_token"] = appservice["as_token"]
registration["hs_token"] = appservice["hs_token"]
registration["url"] = "http://mautrix-signal:29328"

optional_secret_paths = {
  ["provisioning", "shared_secret"] =>
    "provisioning-shared-secret",

  ["public_media", "signing_key"] =>
    "public-media-signing-key",

  ["direct_media", "server_key"] =>
    "direct-media-server-key",

  ["encryption", "pickle_key"] =>
    "encryption-pickle-key",
}

optional_secret_paths.each do |path, filename|
  current = config

  path[0..-2].each do |key|
    unless current[key].is_a?(Hash)
      current = nil
      break
    end

    current = current[key]
  end

  next if current.nil?
  next unless current.key?(path[-1])

  current[path[-1]] = read_secret(
    secret_directory,
    filename,
  )
end

FileUtils.mkdir_p(output_directory)

config_output = File.join(
  output_directory,
  "config.yaml",
)

registration_output = File.join(
  output_directory,
  "registration.yaml",
)

File.write(
  config_output,
  YAML.dump(config),
)

File.write(
  registration_output,
  YAML.dump(registration),
)

File.chmod(0o600, config_output)
File.chmod(0o600, registration_output)

combined = (
  File.read(config_output)
  + File.read(registration_output)
)

if combined.match?(/__[A-Z0-9_]+__/)
  abort("Unresolved template token remains")
end
