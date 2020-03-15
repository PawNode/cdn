# cdn

- certifier
  - serves /.well-known folder on all domains for LE verification
  - r/w object storage encrypted using AES (S3)
    - validations
    - certifiates
    - keys
    - dnssec
- configurator
  - configures varnish (VCL) [TODO]
  - configures nginx
  - configures certifier
    - symlinks global self-signed cert before asking certifier to make sure nginx can load
  - fetches remote content to store locally
- nginx
  - fronts all domains with root (locally stored content) and/or varnish
  - fronts certifier on /.well-known on any domain
- varnish [TODO]
  - used for origin-served domains
