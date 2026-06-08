# Security Policy

## Supported Versions

The OSS fork supports the latest published release and the current development branch.

## Reporting a Vulnerability

If you discover a security issue:

1. Do not open a public issue with exploit details.
2. Contact the maintainers through the private security channel used by the project.
3. Include the affected version, reproduction steps, and impact assessment if possible.

## Security Expectations

- Do not trust client-supplied identity headers for external integrations.
- Keep secrets out of the repository.
- Prefer server-side mapping and authorization for tenant-specific and LMS-specific identities.

