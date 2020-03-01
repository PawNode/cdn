# cdn

- certifier
  - serves /.well-known folder on all domains for LE verification
  - r/w object storage (azure?)
    - validations
  - r/w keyvault (azure? encrypted on object storage?)
    - certificates/keys
- configurator
  - configures varnish (VCL)
  - configures nginx
  - configures contentpuller
  - configures certifier
    - symlinks global self-signed cert before asking certifier to make sure nginx can load
- contentpuller
  - fetches remote content to store locally (periodically? hooks?)
- nginx
  - fronts all domains with root (locally stored content) and/or varnish
  - fronts certifier on /.well-known on any domain
- varnish
  - used for origin-served domains

