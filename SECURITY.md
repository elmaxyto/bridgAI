# Security Policy

BridgAI processes local project files, imported archives, generated patches, and optional external integrations. Security reports are taken seriously.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |
| Earlier versions | No |

Only the latest public release receives security fixes unless otherwise stated.

## Reporting a vulnerability

Do **not** open a public GitHub issue for a vulnerability.

Use GitHub's private vulnerability reporting feature:

1. open the repository's **Security** tab;
2. choose **Report a vulnerability**;
3. provide a clear description and reproduction steps.

Include the affected version, operating system, Python version, attack scenario, proof-of-concept input, expected/actual behavior, affected components, and possible mitigation when available.

Do not include unrelated private source code, credentials, tokens, or personal data.

## Security boundaries

BridgAI keeps filesystem authority in the local application and requires explicit approval before applying changes. However:

- AI-generated code may still be incorrect or malicious;
- imported ZIP files and patches must still be reviewed;
- external AI services receive any content the user deliberately shares;
- localhost services should not be exposed directly to untrusted networks;
- local machine compromise is outside BridgAI's protection boundary;
- users remain responsible for backups and repository review.

Please allow reasonable time for investigation and remediation before public disclosure.
