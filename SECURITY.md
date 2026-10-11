# Security policy

EpochCut is a prototype. Security-sensitive changes should be tested against
the documented graph, authority and effect-boundary assumptions.

## Report privately

Do not post an unpatched vulnerability, credential or production exploit in a
public issue. Send a report to `chandrasen.pandey@ddn.upes.ac.in` containing the
affected component, assumed graph and policy, minimal reproduction steps, and
observed versus expected behaviour. Identify any sensitive data in the report.

## Credentials and private files

Keep credentials outside version control. Local HTTP test keys are generated
test inputs, not production identities. Rotate a credential if it appears in a
commit, archive, terminal capture or message.

Publication sources, submission files and research-result archives belong in a
separate private workspace. The repository checker and CI reject these file
categories. Ignored files must not be force-added to bypass that boundary.

## Prototype boundary

EpochCut assumes complete graph reporting, trusted enforcement points and
exclusive access to protected effects through the broker. The loopback HTTP
services and optional MCP connector write sandbox records. They do not send
real email or manage real identities. Do not expose the HTTP prototype on a
remote interface or treat its local transaction as external exactly-once delivery.
