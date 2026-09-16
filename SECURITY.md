# Security policy

## Supported version

EpochCut is a research prototype. Security fixes are applied to the current
`0.1.x` line; no long-term support promise is made.

## Reporting a vulnerability

Please do not disclose an unpatched vulnerability, credential, or production
exploit in a public issue. Send a concise report to
`chandrasen.pandey@ddn.upes.ac.in` with:

- the affected revision and component;
- the assumed graph, policy, and trust boundary;
- minimal reproduction steps;
- the observed effect and expected behavior; and
- whether the report contains sensitive data.

The maintainers should acknowledge a complete report within seven days. A
research prototype may not receive an immediate patch, but verified findings
will be preserved and scoped accurately.

## Credential handling

Hosted evaluation scripts read provider credentials from environment variables
or an interactive prompt. They must never be committed, copied into protocol
files, embedded in transcripts, or added to issue reports. Rotate a credential
immediately if it appears in a terminal capture, archive, commit, or message.

## Security boundary

EpochCut establishes conditional path closure for declared influence graphs.
It assumes complete instrumentation and trusted enforcement points. The current
MCP effect services are persistent but sandboxed; they are not real email,
identity, payment, or production infrastructure. Reports that challenge these
assumptions are valuable, but the repository does not claim protection outside
the documented boundary.
