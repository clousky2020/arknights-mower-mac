---
format: decision
title: Restart the bound guest system when the instance lifecycle is untouchable
status: implemented
category: feature
date: 2026-11-05
---

# Restart the bound guest system when the instance lifecycle is untouchable

[中文](2026-11-05-guest-restart-with-fault-notices.zh.md)

## Problem

A confirmed UI failure — Android accepting commands while input dispatch stays unresponsive — was repaired only for presets whose manager can re-create the bound instance. Every other preset, including `manual.other`, `manual.physical` and the AVD presets, failed the restart guard and returned one controlled failure. The desktop runtime then entered the recovery loop that retries every thirty seconds, which produced only log warnings and never changed the device state by itself. On 2026-11-04 and 2026-11-05 this condition lasted from the first detection until the user restarted Mower by hand, roughly one hour and eight hours respectively.

The bound preset exposes no owned lifecycle for those targets. An AVD preset refuses `start` until the user confirms it and refuses `stop` because the instance outlives Mower, and a manual target may have been launched by a helper this process cannot re-create. The guard therefore encoded a real constraint: without ownership, a stop or a launch would act on an instance whose re-creation is not guaranteed, and the existing idle-lifecycle rule forbids substituting a host-level command for an unowned control.

Users need the desktop runtime to repair this condition itself, and they need to learn about it: a repair path that can stay blocked for hours produces no other user-visible change, so silence is indistinguishable from a healthy run.

## Decision

[Device Control](../../../../docs/subsystems/device-control.md#12-session-lifecycle-devicesession) owns the restart boundary. When a confirmed UI failure cannot use the owned instance lifecycle, the session restarts the Android system inside the bound endpoint with `adb reboot` instead of returning the controlled failure. The instance, its endpoint identity and its serial survive that restart, so the same Instance Binding comes back and no manager ownership is required. The guard still rejects a changed or unresolvable binding: an endpoint that cannot be resolved to one serial keeps the controlled failure, because a guest restart there would not identify which device it acted on.

`ProductionSessionADB.reboot` performs the command; `DeviceSession._restart_in_device` owns the ordering. The failure record permits only one reboot, mirroring the existing one-shutdown rule, so repeated recovery calls within the same Recovery Budget wait for readiness instead of issuing another command. A session whose ADB port exposes no reboot method keeps the controlled failure, which preserves the existing replaced-backend boundary.

The desktop runtime owns the notification pair. `_notify_ui_fault` sends one ERROR notification before repair begins, because the repair may stay blocked without producing any other user-visible state change. Repeated failures inside the following ten minutes belong to the event that first notification opened and send no further fault mail. `_notify_ui_recovered` sends one matching notification when recovery returns, and requires an open fault notification, so an ordinary restart, a shutdown or a recovery without a preceding notice sends none. A notification failure never prevents the repair. Both notices use the ERROR level, which the existing configured notification level passes through.

## Alternatives considered

- **Keep the controlled failure and rely on the user:** This is the previous behavior. It is honest about the missing ownership, but it leaves unattended operation permanently dependent on a manual restart, and the observed incidents show that the user cannot act on a warning they never receive.
- **Take manager ownership for `manual.other` by guessing a launcher:** The preset names a device the user bound by hand; no manager identity is known for it. Inventing one risks acting on a different instance, which the Instance Binding rule forbids.
- **Run a host-level emulator restart command:** The idle-lifecycle rule explicitly forbids substituting a host-level command for an unowned control, and a host command could terminate an instance the user launched outside Mower. It also cannot work for a physical device.
- **Notify on every recovery cycle:** A blocked repair retries every thirty seconds for hours, so per-cycle mail would flood the mailbox with one incident. Suppressing the fault notice inside a quiet window, while still allowing the recovery notice to close the event, keeps one incident equal to one notification pair.
- **Notify only after a successful recovery:** A successful recovery needs no warning, but a repair that stays blocked for hours would then report nothing at all, which is exactly the silence observed in the incidents.

## Consequences

A confirmed UI failure on a manual, physical or AVD target now reboots the bound Android system and waits for readiness inside the same Recovery Budget, so unattended operation repairs itself instead of stalling until a manual restart. The user receives one notification pair per event, with the fault notice arriving before repair and the recovery notice closing it.

The reboot costs the guest's own uptime: running applications restart, and the game is relaunched by the existing readiness path rather than by the reboot. A device whose input dispatch is broken at the emulator level rather than inside the guest still needs a host-side restart, which remains the user's action. The quiet window is a fixed ten minutes; a genuinely new failure within that window sends no additional fault mail, and the recorded incident time is not reset by it. Recovery still does not establish that the game itself reached a usable scene — the existing recognition boundaries own that.

## Verification

Focused offline suites pass: [device recovery supervision](../../../../arknights_mower/tests/device_recovery_supervision_tests.py) covers the notification pair, the quiet window and a notification failure that leaves the repair running; [UI recovery](../../../../arknights_mower/tests/device_ui_recovery_tests.py) covers the in-place guest restart through the real session ordering, asserting one reboot for the bound serial, no simulator stop or launch, and an unchanged device owner. The combined device session, UI recovery, UI responsiveness, recovery and recovery-supervision suites pass 441 cases and 28 subtests. Python lint passes for the changed modules.

No live device ran the reboot during these checks: the evidence is the offline session ordering, not an observed emulator restart. The 2026-11-04 and 2026-11-05 incidents supply the reported condition, and their manual restarts show that a new ADB session cleared the stuck input channel, which is consistent with but not proof of the guest restart path.
