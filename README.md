# Qiara Home Assistant integration

A custom Home Assistant integration for the **Qiara** security system. It polls
your Qiara hub locally over HTTPS and exposes the alarm panel, door/window and
motion sensors, siren, keypad and camera as Home Assistant entities.

To set it up you need two credentials from your own hub — a **Customer ID** and
a **Secret Key (token)**. Qiara does not surface these in its app, so this guide
walks through extracting them directly from the hub you own, then configuring the
integration.

> ⚠️ **Own device only.** These steps require physical access to your hub and
> give you root on it. Only do this on hardware you own. Opening the enclosure
> and swapping the SD card may void any warranty. Keep the Secret Key / tokens
> and keypad codes confidential — they grant full control of your alarm.

---

## Overview

| Step | What you do |
|------|-------------|
| 1 | Create an SSH key pair on your computer |
| 2 | Open the hub, install the **public** key on its SD card, reinstall |
| 3 | SSH in and extract the account credentials (users + tokens) |
| 4 | Configure the Home Assistant integration with those credentials |

The hub runs Linux from a microSD card (`/dev/mmcblk0`) with three partitions:

| Partition | Mount | Contents |
|-----------|-------|----------|
| `mmcblk0p1` | `/` (root) | OS, `dropbear` SSH, `/root/.ssh/authorized_keys` |
| `mmcblk0p2` | `/data` | `fbxhome.xml*` — the config, incl. accounts & codes |
| `mmcblk0p3` | `/media` | history database |

---

## Step 1 — Create an SSH key

On your computer, generate a dedicated key pair (the hub's dropbear supports
Ed25519):

```bash
ssh-keygen -t ed25519 -C "qiara-hub" -f ~/.ssh/qiara_ed25519
```

This creates two files:

- `~/.ssh/qiara_ed25519` — the **private** key (keep secret, never copy to the hub)
- `~/.ssh/qiara_ed25519.pub` — the **public** key (this is what goes on the hub)

View the public key you'll install in Step 2:

```bash
cat ~/.ssh/qiara_ed25519.pub
```

---

## Step 2 — Install the public key on the hub's SD card

The hub does not accept password SSH by default, so you authorize your key by
editing the SD card offline.

1. **Power off** the hub (unplug it — there is no clean shutdown needed).
2. **Open the enclosure** and remove the **microSD card**. Note its orientation
   so you can reinsert it the same way.
3. **Mount partition 1 (the root filesystem, `ext4`)** on your computer.

   - **On Linux:**
     ```bash
     lsblk                      # identify the card, e.g. /dev/sdb
     sudo mkdir -p /mnt/qiara
     sudo mount /dev/sdb1 /mnt/qiara      # partition 1 = root fs
     ```
   - **On macOS:** macOS cannot write ext4 natively. Use a Linux machine or VM
     (with USB pass-through), or a commercial ext4 driver such as Paragon extFS.
     Read-only tools like `ext4fuse` are **not** enough — you need write access.

4. **Add your public key** to root's `authorized_keys` (create the directory if
   it doesn't exist), then fix ownership/permissions:

   ```bash
   sudo mkdir -p /mnt/qiara/root/.ssh
   cat ~/.ssh/qiara_ed25519.pub | sudo tee -a /mnt/qiara/root/.ssh/authorized_keys
   sudo chown -R 0:0 /mnt/qiara/root/.ssh      # root:root (uid/gid 0)
   sudo chmod 700 /mnt/qiara/root/.ssh
   sudo chmod 600 /mnt/qiara/root/.ssh/authorized_keys
   ```

   > The file may already contain the vendor's keys — **append**, don't overwrite.

5. **Unmount** cleanly, reinsert the card, reassemble the hub, and power it on:

   ```bash
   sudo umount /mnt/qiara
   ```

6. Find the hub's IP on your network (check your router's DHCP leases; the hub
   registers the hostname `lwip`, so it is often reachable as `lwip.localdomain`).
   Confirm SSH works:

   ```bash
   ssh -i ~/.ssh/qiara_ed25519 root@<hub-ip-or-lwip.localdomain>
   ```

   You should get a root shell. Type `exit` to leave.

---

## Step 3 — Retrieve the account credentials

The accounts live in `/data/fbxhome.xml*` as `<AuthToken>` entries — each is a
labeled user with a `cust_id` and a `token` (the token is the integration's
**Secret Key**). Keypad PINs are stored as `<Code>` entries.

Save the script below as `qiara-creds.sh`, make it executable
(`chmod +x qiara-creds.sh`), and run it with your hub's address:

```bash
./qiara-creds.sh <hub-ip-or-lwip.localdomain>
```

Example output:

```
== API accounts ==
   Use one account's cust_id as 'Customer ID' and token as 'Secret Key'.

   Jane Doe                  cust_id=1000  token=xxxxxxxxxxxxxxxx
   John Doe                  cust_id=1000  token=yyyyyyyyyyyyyyyy

== Keypad codes ==
   Front door                PIN=1234
```

Pick any non-discarded API account — its `cust_id` and `token` are what you'll
enter in Step 4.

---

## Step 4 — Configure the Home Assistant integration

1. **Install the integration.** Copy the `custom_components/qiara` folder into
   your Home Assistant `config/custom_components/` directory, then restart Home
   Assistant.

2. **Add the integration.** Go to **Settings → Devices & Services → Add
   Integration**, search for **Qiara**, and fill in the form:

   | Field | Value |
   |-------|-------|
   | **Host** | The hub's IP or hostname, e.g. `192.0.2.10` or `lwip.localdomain` |
   | **Customer ID** | The `cust_id` from Step 3 |
   | **Secret Key** | The `token` from Step 3 |
   | **API port** *(optional)* | Leave blank unless your hub uses a non-standard port (default `64218`) |

3. Submit. The integration validates the credentials and creates the alarm
   panel, sensors, siren, keypad and camera entities.

You can update the host or credentials later via the integration's
**Configure** (options) screen, or it will prompt you to re-authenticate if the
credentials stop working.

---

## Notes

- **Local only.** The integration talks to the hub directly on your LAN over
  HTTPS (self-signed certificate); nothing goes through the cloud.
- **Camera streaming** uses the hub's low-latency SRT feed, restreamed through
  Home Assistant's bundled go2rtc. See the code review docs for details.
- **Keep credentials safe.** Tokens and keypad PINs grant full control of the
  alarm — treat them like passwords.
