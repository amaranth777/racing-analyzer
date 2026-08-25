# Implementation references

- [Nenkai/PDTools](https://github.com/Nenkai/PDTools), MIT: GT7 packet layout, Salsa20, heartbeat `~`, 344-byte PacketType3, XOR key `0x55FABB4F`, flags.
- [snipem/gt7dashboard](https://github.com/snipem/gt7dashboard), GPL-3.0: field offset and wheel-speed relation cross-check only; no source copied.
- [RealJean42/GT7Analyzer](https://github.com/RealJean42/GT7Analyzer): analyzer/package model cross-check.
- [cedricjoulain/gt7](https://github.com/cedricjoulain/gt7): Go telemetry analysis direction.
- [mbm60-max/telemetry-frontend](https://github.com/mbm60-max/telemetry-frontend): session-review and tyre/suspension concepts.

The decoder is an independent Python implementation based on protocol facts and
MIT reference code. GPL-3.0 source is not copied.
