# Pong 6.18.63 history

Szmazwidi maintains and co-develops the port, with implementation,
integration and documentation contributions from OpenAI Codex and
earlier work by Claude. See the [attribution record](https://github.com/Szmazwidi/android_kernel_nothing_sm8475-modules-6.18/blob/pong-a17-6.18.63-wlan-fastrpc/docs/pong-6.18.63-attribution.md)
for links to the original Linux stable, Android ACK and donor commits.

The candidate source SHA qualified for the combined community build is
`7c870eb605a7e2b767b3e52f86ea1e0d7bc897f9`. The
[build recipe](https://github.com/Szmazwidi/android_device_nothing_Pong/tree/pong-6.18-community-wlan-fastrpc/manifests/community-6.18.63-wlan-fastrpc)
pins that SHA. The CI and attribution cleanup changes this note and workflow
files after the qualified source commit.

The historical source integration and early preparation are preserved by
`archive/pong-a17-6.18.63-integration` and
`archive/pong-a17-6.18.63-prep`. The original merge and the applied
io_uring reconciliation are also ancestors of the candidate.
