# Clarification of lateral-lesion semantics

The original README's phrase “blocks lateral spike arrivals” is too broad. From the fork onward, `lateral_off`
prevents creation of new in-plane spike messages. Outgoing-message charges remain. Messages already in flight
are processed normally; vertical spike messages and chemical transport continue. These are the existing rules
in [LIFE_ABI section 12](../../docs/LIFE_ABI.md#12-flags-and-forks), not a change to the simulation.

The measured four-arm interaction therefore concerns added dependence on lateral transmission, including its
possible effects on later development. It does not isolate adult circuit operation or identify a new algorithm.

This clarification was added on 2026-10-13 after the follow-through studies pinned the original archive's
`provenance.json`. The original README and provenance bytes remain unchanged so those studies can reproduce
their exact input identities. This addendum is outside that original provenance manifest.
