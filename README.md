# Webmin Module for DHCP Leases (dnsmasq)

This Webmin module provides a modern, real-time dashboard and administration suite for viewing and managing DHCP leases issued by `dnsmasq` on TurnKey Linux Core (or other Debian-based servers).

The module resides under the **Servers** category in Webmin and is named **DHCP Leases**.

---

## Features

- **Real-Time AJAX Dashboard**: Service state and DHCP leases are monitored and updated dynamically without manual page reloads.
- **Auto-Refresh with LocalStorage Persistence**: Configurable auto-refresh intervals (Off, 5s, 10s, 30s, 60s) that persist across page transitions using the browser's `localStorage` (with automatic cleanup when navigating away to prevent CPU/network loops).
- **Interactive Lease Table**:
  - **Live Countdown Timer**: Lease expiration (epoch times) is converted into a countdown timer that decrements in real time via browser JS.
  - **Sortable Columns**: Click column headers (IP Address, MAC Address, Hostname, Remaining Time, Status) to instantly sort leases.
  - **Live Search & Filter**: Instantly search/filter the lease table across IP, MAC, Hostname, and Manufacturer Vendor fields.
  - **Export CSV**: Click to download the current leases list directly as a spreadsheet-compatible CSV file.
- **Asynchronous MAC Vendor Lookup**:
  - Checks if the MAC address is randomized (locally administered octets).
  - Searches an offline database of common OUIs (Apple, Google, Intel, Raspberry Pi, VMware, QEMU, VirtualBox, etc.) for instant resolution.
  - Asynchronously queries the `api.macvendors.com` API for unrecognized manufacturers, saving results to a local persistent server-side cache (`/etc/webmin/dnsmasq-dhcpleases/mac_vendor_cache`) to avoid future rate limits.
- **One-Click Static Reservations**: Promote any active dynamic lease to a permanent static IP assignment with one click.
  - If a `dhcp-hostsfile` option is defined in dnsmasq, it writes directly to that file and executes a fast `SIGHUP` reload.
  - If no hostsfile is configured, it appends the static `dhcp-host` directive to `dnsmasq.conf` and restarts the daemon.
- **Dynamic Lease Deletion**: Stop the daemon, remove the dynamic lease from `dnsmasq.leases`, and restart the daemon to ensure dnsmasq does not write it back from memory.
- **Capacity Statistics & Status Bar**: Displays cards with Active Leases, Free Pool IPs, and a styled progress bar showing Pool Utilization (calculated from parsed `dhcp-range` configurations).

---

## Installation & Deployment

### 1. Build the Package
From the root of this repository, run the build script:
```bash
python3 build.py
```
This generates the Webmin package file `dnsmasq-dhcpleases.wbm.gz` in the root folder.

### 2. Install on Webmin
1. Log in to the TurnKey Linux Webmin interface (`https://<your-server-ip>:12321/`).
2. Navigate to **Webmin** -> **Webmin Configuration** -> **Webmin Modules** in the left sidebar.
3. Choose **From uploaded file**, click **Choose File**, select `dnsmasq-dhcpleases.wbm.gz` from your local computer, and click **Install Module**.

Once installed, refresh the page and navigate to **Servers** -> **DHCP Leases**.

---

## Custom Configuration
If your server uses custom configuration paths, you can adjust them in Webmin:
1. Open the **DHCP Leases** module.
2. Click the gear icon (**Module Config**) at the top left.
3. Configure the paths:
   - **Path to dnsmasq configuration file** (Default: `/etc/dnsmasq.conf`)
   - **Path to DHCP leases file** (Default: `/var/lib/misc/dnsmasq.leases`)
   - **Systemd service name** (Default: `dnsmasq`)
4. Click **Save**.
