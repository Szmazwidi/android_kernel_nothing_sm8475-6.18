# Nothing Phone (2) — Android 17 / Linux 6.18.60 source candidate

This branch extends the verified `pong-a17-6.18.59` source release with the
signed upstream v6.18.60 tag, commit
`f45ed76d6791cf72ff1265ee93511175bbbc2f18` (113 original stable commits).
Greg Kroah-Hartman's tag signature was checked against the fingerprint
published by kernel.org. ACK/stable history and existing Pong KMI exceptions
remain intact. The eventfs merge retains U59 revert `f0b01f206504`: the new
unlock patch modifies a barrier block absent from that compatibility variant.

The complete 178 vendor + 84 GKI source build, final frozen ABI check,
SHA-256 signing and diskless default-enforcement positive/negative VM tests
passed. **The first native hardware test did not complete Android boot.**
The vendor source recipe had selected the rejected heap974 diagnostic exporter,
which lacked the qcom,system name and userspace mmap. The exact CLS38 / 6.18.59
images were restored with personal data and normal checkpoint state verified.
The companion modules branch subsequently selected heap982, and a complete
source-built 6.18.60 cohort booted the development phone with Android, root,
SELinux enforcing and forced module signatures. Camera CPU access still failed
with EPERM. A later recipe selects the stage1063 heap, matching the working
CLS38 implementation and preserving its permission-ownership checks. A full
262-module rebuild, frozen payload policy, signatures, ABI and admission VM
tests passed for that cohort. It also booted the development phone with data
preserved; mobile data and NDK camera preview/JPEG probes passed. Further
device tests and the open warnings/crashes are recorded in the modules
repository. Remote defaults and the complete-ROM
recipe remain on the 6.18.59 reference unless explicitly updated.

The kernel starts from ACK `android17-6.18-2026-09_r5` plus the preserved U59
stable integration and Pong device changes. A version string is not a claim
that every unmodified mainline feature or patch is present.

The vendor modules for the phone are in
[android_kernel_nothing_sm8475-modules-6.18](https://github.com/Szmazwidi/android_kernel_nothing_sm8475-modules-6.18),
branch `pong-a17-6.18.60`. Its README has the pinned repo manifest and the build steps for both.

## The `pong: LAB:` commits

These commits are safety guards for one particular development phone. They are **not** device
support and they must not be used on any other phone as they are.

| Commit | What it does |
|---|---|
| `pong: LAB: Reject block writes outside the allowed ranges of this UFS` | Every physical BIO is checked; writes, discards and secure erases are allowed only to the userdata/metadata ranges of UFS LUN 0 with the exact capacity of the development phone (487079936 sectors). Everything else fails with `BLK_STS_IOERR`. |
| `pong: LAB: Refuse BSG and SCSI passthrough from userspace` | `bsg_open()` and the SG_IO / SCSI command ioctls return `-EPERM`, so userspace cannot bypass the BIO check. |
| `pong: LAB: Mount protected physical partitions read-only` | Block-device mounts outside the allowed ranges are forced to `SB_RDONLY`. |
| `pong: LAB: Disable kexec_load` | Keeps the guards in place until a normal reboot. |
| `pong: LAB: Load only the verified module payloads` | After the signature check, a module is loaded only if the SHA-256 of its payload is listed in `kernel/module/pong251-module-policy.h` (the module set of the development image). |
| `pong: retain CLS20/21 scoped RPMB and UFS read-query access` | Narrow exception to the BSG lock: only the RPMB W-LUN with the RPMB opcodes (needed by qseecomd, otherwise Gatekeeper cannot enroll a lock screen) and read-only UFS QUERY descriptors/attributes/flags on `/dev/ufs-bsg0`. |
| `pong: retain admitted module payload history through CLS…` | Payload hashes of the modules admitted in later development stages. |

Since stage CLG1 all of the above are compiled only with `CONFIG_PONG_LAB_GUARDS=y`
(`block/Kconfig`, default **off**). The laboratory profile enables it through the
defconfig fragment `arch/arm64/configs/pong_lab.fragment`:

```sh
# laboratory kernel for the development phone (guards on)
tools/bazel run --defconfig_fragment=//common:pong_lab_defconfig //common:kernel_aarch64_dist -- --destdir=out/kernel-lab
# default / release kernel (guards compiled out, plain upstream behaviour)
tools/bazel run //common:kernel_aarch64_dist -- --destdir=out/kernel
```

With the option off the BIO/mount hooks become empty inline stubs, `bsg_open()`, SG_IO and the
SCSI ioctls behave as upstream, `kexec_load` is not pre-disabled and the module loader relies on
signature enforcement only (`CONFIG_MODULE_SIG_FORCE=y` stays in `gki_defconfig`). The payload
list `kernel/module/pong251-module-policy.h` is compiled only in the laboratory profile.

Consequences (laboratory profile):

* On another phone (different UFS size or partition layout) the block guard rejects writes
  that Android needs.
* Modules you build yourself are refused (`PONG276_MODULE_PAYLOAD_DENIED` in the kernel log)
  unless their payloads are in the list. Even a rebuild from the same sources differs in
  `.BTF`, because module BTF depends on `vmlinux`.

Identify the guard commits separately from the device-support commits:

```sh
git log --oneline --first-parent 926a323dc266..HEAD   # list the pong: commits
# Review only the specific LAB guard commits for your hardware geometry.
```

Do not revert every `pong:` commit: that also removes port support. Keep the guards
for this development phone; for other hardware, review partition geometry first.
Regenerate the module list from the modules you ship with
`tools/gen-module-policy.py` from the modules repository, rebuild the kernel, and re-sign the
modules with its key. The modules repository README has the exact steps.

## Module signing and source verification

Standalone source builds now select `CONFIG_MODULE_SIG_FORCE=y` and SHA-256,
with automatic GKI signing retained. BoringSSL's PKCS#7 API emits RSA/SHA-256;
the sign-file compatibility check now accepts that correctly and retains the
legacy Android build-utils argument as an explicit SHA-256 alias. The old
OpenSSL fallback and all KMI checks remain in place. Raw-signature mode does
not dereference an absent hash argument. See the
[BoringSSL API contract](https://boringssl.googlesource.com/boringssl/+/89386ac89bef26888b8d866ebb98b696d82dfde8/include/openssl/pkcs7.h).

The source/ABI check covers all 262 selected modules. The fresh two-pass bank
has verified SHA-256 signatures, and a diskless VM checks default enforcement,
valid module admission, and rejection of unsigned, unknown-key, damaged and
changed-payload modules. These are host results, separate from the historical
CLS38 hardware Image, whose signature-force parameter was off while its exact
payload gate was active. A fresh locally keyed 6.18.60 cohort booted Android
on the development phone; that boot alone does not establish camera or other
hardware functionality. The subsequent stage1063 heap cohort is a separate
build whose limited camera and mobile results are documented by the modules
repository; other devices and features still require qualification.

## Building

Inside the Kleaf workspace described in the modules repository:

```sh
tools/bazel run //common:kernel_aarch64_dist -- --destdir=out/kernel
```

Without `--config=stamp` the kernel release is
`6.18.60-android17-5-maybe-dirty-4k`. A fresh build generates its own signing key;
the phone's private key is not published. The newly verified Image and module
bank are source-build evidence, not byte-identical replacements for CLS38.
Use the complete two-pass instructions in the modules repository before
packaging new modules with their matching Image and key.

## Authorship

The full ACK and stable v6.18.59 history is kept; nothing below `926a323dc266` or in the
stable merge parent was changed. The `pong:` commits and the U59 integration are by Szmazwidi; they were written with OpenAI Codex and prepared for publication with Claude,
as their trailers state.
