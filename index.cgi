#!/usr/bin/perl
# index.cgi
# Main dashboard for viewing and managing DHCP leases issued by dnsmasq on TurnKey Core.

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

# Read version from module.info
my $version = "1.0.0";
if (open(my $vfh, "<", "./module.info")) {
    while(my $line = <$vfh>) {
        if ($line =~ /^version=(.*)$/) {
            $version = $1;
            $version =~ s/\r?\n//;
            last;
        }
    }
    close($vfh);
}

&ui_print_header(undef, $text{'index_title'} . " v" . $version, "", undef, 1, 1);

# 1. Action/Service Toolbar & Refresh Controls
my ($running, $enabled) = &get_service_status();

print "
<div style='margin-bottom: 20px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 15px;'>
  <!-- Service Controls -->
  <div>
    <form action='action.cgi' method='post' style='display: inline-block; margin: 0;'>
      <span id='status-display'>" . ($running ? 
          "<span style='color:green; font-weight:bold; font-size:1.15em; margin-right: 15px;'><i class='fa fa-circle'></i> $text{'index_running'}</span>" :
          "<span style='color:red; font-weight:bold; font-size:1.15em; margin-right: 15px;'><i class='fa fa-circle-o'></i> $text{'index_stopped'}</span>") . "</span>
      <span id='control-buttons-container'>";
      if ($running) {
          print &ui_submit($text{'index_stop'}, "stop", undef, undef, "class='btn btn-danger btn-sm'");
          print " " . &ui_submit($text{'index_restart'}, "restart", undef, undef, "class='btn btn-warning btn-sm'");
      } else {
          print &ui_submit($text{'index_start'}, "start", undef, undef, "class='btn btn-success btn-sm'");
      }
print "</span>
      <span style='margin-left: 20px; display: inline-block;'>
        " . &ui_checkbox("boot", 1, $text{'index_boot'}, $enabled, "onclick='form.submit()'") . "
      </span>
    </form>
  </div>

  <!-- Auto Refresh Controls -->
  <div style='display: flex; align-items: center; gap: 10px;'>
    <button id='manual-refresh-btn' class='btn btn-default btn-sm' onclick='updateStatusAjax(true)' style='margin: 0; padding: 4px 10px;'>
      <i class='fa fa-refresh'></i> $text{'index_refresh'}
    </button>
    <span style='font-size: 0.9em; color: #666;'>$text{'index_auto_refresh'}</span>
    <select id='auto-refresh-select' class='form-control input-sm' style='width: 120px; display: inline-block; margin: 0; height: 30px; padding: 2px 6px;' onchange='changeAutoRefresh(this.value)'>
      <option value='off'>Off</option>
      <option value='5'>5 seconds</option>
      <option value='10'>10 seconds</option>
      <option value='30'>30 seconds</option>
      <option value='60'>60 seconds</option>
    </select>
    <span style='font-size: 0.9em; color: #666; margin-left: 15px;'>$text{'index_scope'}</span>
    <select id='scope-filter-select' class='form-control input-sm' style='width: 160px; display: inline-block; margin: 0; height: 30px; padding: 2px 6px;' onchange='changeScopeFilter(this.value)'>
      <option value='all'>All Scopes</option>
    </select>
    <span id='refresh-spinner' style='display: none; color: #0284c7; margin-left: 5px;'><i class='fa fa-spinner fa-spin'></i></span>
  </div>
</div>
";

# 2. Pool Statistics Cards Dashboard
print "
<div class='row'>
  <div class='col-sm-4'>
    <div class='panel panel-default' style='margin-bottom:15px; border-left: 4px solid #0284c7; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
      <div class='panel-body' style='padding: 15px;'>
        <div style='font-size: 0.9em; text-transform: uppercase; color: #666; font-weight: bold;'>$text{'index_active_leases'}</div>
        <div id='stat-active' style='font-size: 2.2em; font-weight: bold; color: #0284c7; margin-top: 5px;'>0</div>
      </div>
    </div>
  </div>
  <div class='col-sm-4'>
    <div class='panel panel-default' style='margin-bottom:15px; border-left: 4px solid #10b981; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
      <div class='panel-body' style='padding: 15px;'>
        <div style='font-size: 0.9em; text-transform: uppercase; color: #666; font-weight: bold;'>$text{'index_free_ips'}</div>
        <div id='stat-free' style='font-size: 2.2em; font-weight: bold; color: #10b981; margin-top: 5px;'>0</div>
      </div>
    </div>
  </div>
  <div class='col-sm-4'>
    <div class='panel panel-default' style='margin-bottom:15px; border-left: 4px solid #f59e0b; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
      <div class='panel-body' style='padding: 15px;'>
        <div style='font-size: 0.9em; text-transform: uppercase; color: #666; font-weight: bold;'>$text{'index_utilization'}</div>
        <div style='display: flex; align-items: baseline; justify-content: space-between; margin-top: 5px;'>
          <span id='stat-utilization' style='font-size: 2.2em; font-weight: bold; color: #f59e0b;'>0%</span>
          <span id='stat-total-desc' style='font-size: 0.95em; color: #666;'>of 0 total IPs</span>
        </div>
        <div class='progress progress-xs' style='margin: 8px 0 0 0; height: 6px;'>
          <div id='utilization-progress' class='progress-bar progress-bar-warning' role='progressbar' style='width: 0%; transition: width 0.6s ease; background-color: #f59e0b;'></div>
        </div>
      </div>
    </div>
  </div>
</div>
<br>
";

# 3. Dynamic Leases Table Toolbar and Box
print "
<div class='panel panel-default' style='box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
  <div class='panel-heading' style='background: #fafafa; border-bottom: 1px solid #eee; padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;'>
    <h3 class='panel-title' style='font-size: 1.15em; font-weight: bold; margin: 0;'>$text{'index_leases'}</h3>
    <div style='display: flex; align-items: center; gap: 10px;'>
      <div style='position: relative; display: inline-block;'>
        <span style='margin-right: 5px; font-weight: normal; color: #555;'>$text{'index_search'}</span>
        <input type='text' id='search-input' class='form-control input-sm' style='width: 180px; display: inline-block; padding-left: 8px; border-radius: 4px; height: 30px;' placeholder='Search...' onkeyup='handleSearch(this.value)'>
      </div>
      <button class='btn btn-info btn-sm' onclick='exportCSV()' style='margin: 0; height: 30px;'><i class='fa fa-file-excel-o'></i> $text{'index_export'}</button>
    </div>
  </div>
  
  <div class='table-responsive'>
    <table class='table table-striped table-hover table-bordered ui_table' style='margin: 0;'>
      <thead>
        <tr class='ui_table_head'>
          <th style='cursor: pointer;' onclick='handleSort(\"ip\")'>$text{'index_ip'} <span id='sort-icon-ip' class='fa fa-sort text-muted'></span></th>
          <th style='cursor: pointer;' onclick='handleSort(\"mac\")'>$text{'index_mac'} <span id='sort-icon-mac' class='fa fa-sort text-muted'></span></th>
          <th>$text{'index_vendor'}</th>
          <th style='cursor: pointer;' onclick='handleSort(\"hostname\")'>$text{'index_host'} <span id='sort-icon-hostname' class='fa fa-sort text-muted'></span></th>
          <th style='cursor: pointer;' onclick='handleSort(\"remaining\")'>$text{'index_expiry'} <span id='sort-icon-remaining' class='fa fa-sort text-muted'></span></th>
          <th style='cursor: pointer;' onclick='handleSort(\"type\")'>$text{'index_status_col'} <span id='sort-icon-type' class='fa fa-sort text-muted'></span></th>
          <th>$text{'index_action'}</th>
        </tr>
      </thead>
      <tbody id='leases-table-body'>
        <tr>
          <td colspan='7' style='text-align: center; padding: 20px; color: #888;'>
            <i class='fa fa-spinner fa-spin'></i> Loading leases...
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
<br>
";

# 4. Configured Static Reservations Table Box
print "
<div class='panel panel-default' style='box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
  <div class='panel-heading' style='background: #fafafa; border-bottom: 1px solid #eee; padding: 10px 15px;'>
    <h3 class='panel-title' style='font-size: 1.15em; font-weight: bold; margin: 0;'>$text{'index_static_title'}</h3>
  </div>
  
  <div class='table-responsive'>
    <table class='table table-striped table-hover table-bordered ui_table' style='margin: 0;'>
      <thead>
        <tr class='ui_table_head'>
          <th style='cursor: pointer;' onclick='handleStaticSort(\"ip\")'>$text{'index_ip'} <span id='ssort-icon-ip' class='fa fa-sort text-muted'></span></th>
          <th style='cursor: pointer;' onclick='handleStaticSort(\"mac\")'>$text{'index_mac'} <span id='ssort-icon-mac' class='fa fa-sort text-muted'></span></th>
          <th style='cursor: pointer;' onclick='handleStaticSort(\"hostname\")'>$text{'index_host'} <span id='ssort-icon-hostname' class='fa fa-sort text-muted'></span></th>
          <th>Source</th>
          <th>$text{'index_action'}</th>
        </tr>
      </thead>
      <tbody id='statics-table-body'>
        <tr>
          <td colspan='5' style='text-align: center; padding: 20px; color: #888;'>
            <i class='fa fa-spinner fa-spin'></i> Loading reservations...
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
";

# 5. Client side SPA Logic
print <<'JS_EOF';
<script type='text/javascript'>
// Global state
let leasesState = [];
let staticsState = [];
let statsState = { total: 0, active: 0, free: 0, utilization: "0" };
let rangesState = [];
let selectedScope = "all";

let searchQuery = "";
let sortKey = "ip";
let sortOrder = "asc";

let staticSortKey = "ip";
let staticSortOrder = "asc";

// Persistence timers
if (window.dhcpLeaseRefreshTimer) {
    clearInterval(window.dhcpLeaseRefreshTimer);
    window.dhcpLeaseRefreshTimer = null;
}

// IP comparator helper for sorting
function compareIPs(ipA, ipB) {
    const a = ipA.split('.').map(Number);
    const b = ipB.split('.').map(Number);
    for (let i = 0; i < 4; i++) {
        if (a[i] < b[i]) return -1;
        if (a[i] > b[i]) return 1;
    }
    return 0;
}

// Sort algorithm
function sortData(data, key, order, isIP = false) {
    return data.sort((a, b) => {
        let valA = a[key] || '';
        let valB = b[key] || '';
        
        if (isIP) {
            return order === 'asc' ? compareIPs(valA, valB) : compareIPs(valB, valA);
        }
        
        if (key === 'remaining' || key === 'expiry' || key === 'line') {
            valA = Number(valA);
            valB = Number(valB);
        } else {
            valA = String(valA).toLowerCase();
            valB = String(valB).toLowerCase();
        }
        
        if (valA < valB) return order === 'asc' ? -1 : 1;
        if (valA > valB) return order === 'asc' ? 1 : -1;
        return 0;
    });
}

// Format seconds into hh:mm:ss or expired label
function formatRemainingTime(seconds) {
    if (seconds <= 0) {
        return `<span class="label label-danger" style="padding: 3px 8px; border-radius: 3px; font-weight: bold;">Expired</span>`;
    }
    
    if (seconds >= 86400) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        return `${days}d ${hours}h ${mins}m ${secs}s`;
    }
    
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${mins}m ${secs}s`;
}

// OUI Vendor Resolution caching proxy
const vendorCache = {};
function resolveVendor(mac, cellId) {
    const cleanMac = mac.toLowerCase();
    
    // 1. Check local memory cache
    if (vendorCache[cleanMac]) {
        const el = document.getElementById(cellId);
        if (el) el.innerHTML = vendorCache[cleanMac];
        return;
    }
    
    // 2. Check browser LocalStorage
    const cached = localStorage.getItem(`oui_vendor_${cleanMac}`);
    if (cached) {
        vendorCache[cleanMac] = cached;
        const el = document.getElementById(cellId);
        if (el) el.innerHTML = cached;
        return;
    }
    
    // 3. Query the CGI offline/online proxy
    fetch(`mac_lookup.cgi?mac=${encodeURIComponent(mac)}`)
        .then(res => res.json())
        .then(data => {
            const vendor = data.vendor || 'Unknown';
            vendorCache[cleanMac] = vendor;
            localStorage.setItem(`oui_vendor_${cleanMac}`, vendor);
            const el = document.getElementById(cellId);
            if (el) el.innerHTML = vendor;
        })
        .catch(err => {
            console.error('Vendor lookup error for ' + mac, err);
            const el = document.getElementById(cellId);
            if (el) el.innerHTML = 'Unknown';
        });
}

// Fetch status via AJAX
function updateStatusAjax(isManual) {
    const spinner = document.getElementById('refresh-spinner');
    if (spinner) spinner.style.display = 'inline-block';
    
    fetch('status_ajax.cgi')
        .then(response => response.json())
        .then(data => {
            // 1. Update service status indicators
            const statusDisp = document.getElementById('status-display');
            if (statusDisp) {
                statusDisp.innerHTML = data.running ? 
                    `<span style="color:green; font-weight:bold; font-size:1.15em; margin-right: 15px;"><i class="fa fa-circle"></i> Active (Running)</span>` :
                    `<span style="color:red; font-weight:bold; font-size:1.15em; margin-right: 15px;"><i class="fa fa-circle-o"></i> Stopped</span>`;
            }
            
            const btnContainer = document.getElementById('control-buttons-container');
            if (btnContainer) {
                if (data.running) {
                    btnContainer.innerHTML = `
                        <input type="submit" name="stop" value="Stop DHCP Service" class="btn btn-danger btn-sm">
                        <input type="submit" name="restart" value="Restart DHCP Service" class="btn btn-warning btn-sm">
                    `;
                } else {
                    btnContainer.innerHTML = `<input type="submit" name="start" value="Start DHCP Service" class="btn btn-success btn-sm">`;
                }
            }
            
            // 2. Save stats, ranges, and update display
            statsState = data.stats;
            rangesState = data.ranges || [];
            updateScopeSelectorOptions();
            updateStatsDisplay();
            
            // 3. Save states & render tables
            leasesState = data.leases;
            staticsState = data.statics;
            
            renderLeasesTable();
            renderStaticsTable();
        })
        .catch(err => console.error('Error loading leases data:', err))
        .finally(() => {
            if (spinner) spinner.style.display = 'none';
        });
}

function intToIp(num) {
    return [
        (num >>> 24) & 255,
        (num >>> 16) & 255,
        (num >>> 8) & 255,
        num & 255
    ].join('.');
}

function maskToCidr(mask) {
    const maskInt = ipToInt(mask);
    let count = 0;
    for (let i = 0; i < 32; i++) {
        if ((maskInt >>> i) & 1) {
            count++;
        }
    }
    return count;
}

function getSubnetRange(ip, mask) {
    const ipInt = ipToInt(ip);
    const maskInt = ipToInt(mask);
    const netInt = (ipInt & maskInt) >>> 0;
    const broadcastInt = (netInt | (~maskInt)) >>> 0;
    
    return {
        net: intToIp(netInt),
        broadcast: intToIp(broadcastInt),
        netInt: netInt,
        broadcastInt: broadcastInt
    };
}

function ipToInt(ip) {
    const parts = ip.split('.').map(Number);
    return ((parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]) >>> 0;
}

function changeScopeFilter(val) {
    selectedScope = val;
    updateStatsDisplay();
    renderLeasesTable();
    renderStaticsTable();
}

function updateStatsDisplay() {
    let displayStats = Object.assign({}, statsState);
    
    if (selectedScope !== 'all') {
        const range = rangesState.find(r => r.start === selectedScope);
        if (range) {
            const startInt = ipToInt(range.start);
            const endInt = ipToInt(range.end);
            const total = endInt - startInt + 1;
            
            let active = 0;
            leasesState.forEach(l => {
                const ipInt = ipToInt(l.ip);
                if (ipInt >= startInt && ipInt <= endInt) {
                    active++;
                }
            });
            
            const free = Math.max(0, total - active);
            const utilization = total > 0 ? ((active / total) * 100).toFixed(1) : "0";
            
            displayStats = { total, active, free, utilization };
        }
    }
    
    document.getElementById('stat-active').innerHTML = displayStats.active;
    document.getElementById('stat-free').innerHTML = displayStats.free;
    document.getElementById('stat-utilization').innerHTML = displayStats.utilization + '%';
    document.getElementById('stat-total-desc').innerHTML = `of ${displayStats.total} total IPs`;
    
    const progress = document.getElementById('utilization-progress');
    if (progress) {
        progress.style.width = displayStats.utilization + '%';
        const util = parseFloat(displayStats.utilization);
        if (util > 90) {
            progress.style.backgroundColor = '#ef4444';
        } else if (util > 75) {
            progress.style.backgroundColor = '#f59e0b';
        } else {
            progress.style.backgroundColor = '#10b981';
        }
    }
}

function updateScopeSelectorOptions() {
    const select = document.getElementById('scope-filter-select');
    if (!select) return;
    
    const currentVal = select.value;
    

    select.innerHTML = `<option value="all">All Scopes</option>`;
    rangesState.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.start;
        const subnet = getSubnetRange(r.start, r.netmask);
        const cidr = maskToCidr(r.netmask);
        opt.innerText = `${subnet.net}/${cidr} (${r.start} - ${r.end})`;
        select.appendChild(opt);
    });
    
    let hasCurrent = false;
    for (let i = 0; i < select.options.length; i++) {
        if (select.options[i].value === currentVal) {
            hasCurrent = true;
            break;
        }
    }
    if (hasCurrent) {
        select.value = currentVal;
    } else {
        select.value = 'all';
        selectedScope = 'all';
    }
}

// Render active leases
function renderLeasesTable() {
    const tbody = document.getElementById('leases-table-body');
    if (!tbody) return;
    
    // Filter
    let filtered = leasesState.filter(l => {
        if (selectedScope !== 'all') {
            const range = rangesState.find(r => r.start === selectedScope);
            if (range) {
                const ipInt = ipToInt(l.ip);
                const subnet = getSubnetRange(range.start, range.netmask);
                if (ipInt < subnet.netInt || ipInt > subnet.broadcastInt) {
                    return false;
                }
            }
        }
        const query = searchQuery.toLowerCase();
        const vendor = vendorCache[l.mac.toLowerCase()] || '';
        return l.ip.toLowerCase().includes(query) ||
               l.mac.toLowerCase().includes(query) ||
               vendor.toLowerCase().includes(query) ||
               l.hostname.toLowerCase().includes(query);
    });
    
    // Sort
    const isIP = (sortKey === 'ip');
    sortData(filtered, sortKey, sortOrder, isIP);
    
    // Update header sort icons
    updateSortIcons();
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: #888;">No active DHCP leases found.</td></tr>`;
        return;
    }
    
    let html = "";
    filtered.forEach(l => {
        const macId = l.mac.replace(/:/g, '-');
        const cellId = `vendor-${macId}`;
        const expiryCellId = `expiry-${macId}`;
        
        // Type Badge
        const typeBadge = l.type === 'static' ? 
            `<span class="label label-success" style="padding: 2px 6px; border-radius: 3px; font-weight: bold;"><i class="fa fa-lock"></i> Static</span>` :
            `<span class="label label-info" style="padding: 2px 6px; border-radius: 3px; font-weight: bold;"><i class="fa fa-globe"></i> Dynamic</span>`;
            
        // Action Buttons
        let actions = "";
        if (l.type === 'static') {
            actions = `
                <a href="delete_reservation.cgi?mac=${encodeURIComponent(l.mac)}&ip=${encodeURIComponent(l.ip)}" class="btn btn-default btn-xs text-danger" title="Remove Static Reservation" onclick="return confirm('Are you sure you want to remove the static reservation for ${l.mac}?')">
                    <i class="fa fa-trash"></i> Delete Res.
                </a>
            `;
        } else {
            actions = `
                <a href="save_reservation.cgi?mac=${encodeURIComponent(l.mac)}&ip=${encodeURIComponent(l.ip)}&hostname=${encodeURIComponent(l.hostname)}" class="btn btn-success btn-xs" title="Convert to Static Reservation">
                    <i class="fa fa-lock"></i> Reserve
                </a>
                <a href="delete_lease.cgi?mac=${encodeURIComponent(l.mac)}&ip=${encodeURIComponent(l.ip)}" class="btn btn-danger btn-xs" title="Delete Lease" onclick="return confirm('Are you sure you want to stop the service and delete this active lease? This requires a service reboot.')" style="margin-left: 5px;">
                    <i class="fa fa-times"></i> Delete Lease
                </a>
            `;
        }
        
        html += `
            <tr>
                <td><b>${l.ip}</b></td>
                <td><code style="font-size:0.95em; color:#333;">${l.mac}</code></td>
                <td id="${cellId}"><span style="color:#aaa;">Loading...</span></td>
                <td>${l.hostname ? `<b>${l.hostname}</b>` : '<i style="color:#999;">Unnamed</i>'}</td>
                <td id="${expiryCellId}">${formatRemainingTime(l.remaining)}</td>
                <td>${typeBadge}</td>
                <td>${actions}</td>
            </tr>
        `;
        
        // Resolve vendor asynchronously
        setTimeout(() => resolveVendor(l.mac, cellId), 0);
    });
    
    tbody.innerHTML = html;
}

// Render configured static reservations
function renderStaticsTable() {
    const tbody = document.getElementById('statics-table-body');
    if (!tbody) return;
    
    // Filter
    let filteredStatics = staticsState.slice();
    if (selectedScope !== 'all') {
        const range = rangesState.find(r => r.start === selectedScope);
        if (range) {
            const subnet = getSubnetRange(range.start, range.netmask);
            filteredStatics = filteredStatics.filter(s => {
                if (!s.ip) return false;
                const ipInt = ipToInt(s.ip);
                return ipInt >= subnet.netInt && ipInt <= subnet.broadcastInt;
            });
        }
    }
    
    // Sort
    const isIP = (staticSortKey === 'ip');
    sortData(filteredStatics, staticSortKey, staticSortOrder, isIP);
    
    // Update static header icons
    updateStaticSortIcons();
    
    if (filteredStatics.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #888;">No static reservations configured.</td></tr>`;
        return;
    }
    
    let html = "";
    filteredStatics.forEach(s => {
        html += `
            <tr>
                <td><b>${s.ip}</b></td>
                <td><code style="font-size:0.95em; color:#333;">${s.mac}</code></td>
                <td>${s.hostname ? `<b>${s.hostname}</b>` : '<i style="color:#999;">None</i>'}</td>
                <td><span class="label label-default" style="text-transform: capitalize; font-weight: normal;">${s.source}</span></td>
                <td>
                    <a href="delete_reservation.cgi?mac=${encodeURIComponent(s.mac)}&ip=${encodeURIComponent(s.ip)}" class="btn btn-default btn-xs text-danger" title="Delete Reservation" onclick="return confirm('Are you sure you want to delete this static reservation?')">
                        <i class="fa fa-trash"></i> Delete Res.
                    </a>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// Dynamic Search Handler
function handleSearch(val) {
    searchQuery = val;
    renderLeasesTable();
}

// Sorting for Leases
function handleSort(key) {
    if (sortKey === key) {
        sortOrder = (sortOrder === 'asc') ? 'desc' : 'asc';
    } else {
        sortKey = key;
        sortOrder = 'asc';
    }
    renderLeasesTable();
}

// Sorting for Statics
function handleStaticSort(key) {
    if (staticSortKey === key) {
        staticSortOrder = (staticSortOrder === 'asc') ? 'desc' : 'asc';
    } else {
        staticSortKey = key;
        staticSortOrder = 'asc';
    }
    renderStaticsTable();
}

// Update UI sort headers
function updateSortIcons() {
    ['ip', 'mac', 'hostname', 'remaining', 'type'].forEach(k => {
        const el = document.getElementById(`sort-icon-${k}`);
        if (!el) return;
        
        if (sortKey === k) {
            el.className = `fa fa-sort-${sortOrder === 'asc' ? 'asc' : 'desc'} text-primary`;
        } else {
            el.className = 'fa fa-sort text-muted';
        }
    });
}

function updateStaticSortIcons() {
    ['ip', 'mac', 'hostname'].forEach(k => {
        const el = document.getElementById(`ssort-icon-${k}`);
        if (!el) return;
        
        if (staticSortKey === k) {
            el.className = `fa fa-sort-${staticSortOrder === 'asc' ? 'asc' : 'desc'} text-primary`;
        } else {
            el.className = 'fa fa-sort text-muted';
        }
    });
}

// CSV Export
function exportCSV() {
    let csv = 'IP Address,MAC Address,Hostname,Remaining Lease Time,Type\n';
    leasesState.forEach(l => {
        const typeLabel = l.type === 'static' ? 'Static' : 'Dynamic';
        const remTime = l.remaining > 0 ? 
            `${Math.floor(l.remaining/3600)}h ${Math.floor((l.remaining%3600)/60)}m ${l.remaining%60}s` : 'Expired';
        csv += `"${l.ip}","${l.mac}","${l.hostname}","${remTime}","${typeLabel}"\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", "dhcp_leases.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Manage Refresh state
function changeAutoRefresh(val) {
    localStorage.setItem('dhcpleases_refresh_interval', val);
    if (window.dhcpLeaseRefreshTimer) {
        clearInterval(window.dhcpLeaseRefreshTimer);
        window.dhcpLeaseRefreshTimer = null;
    }
    if (val !== 'off') {
        const sec = parseInt(val, 10);
        updateStatusAjax(false); // Fetch immediately on interval change
        window.dhcpLeaseRefreshTimer = setInterval(function() {
            const select = document.getElementById('auto-refresh-select');
            if (!select) {
                // Clear background timer if user navigated away via PJAX
                clearInterval(window.dhcpLeaseRefreshTimer);
                window.dhcpLeaseRefreshTimer = null;
                return;
            }
            updateStatusAjax(false);
        }, sec * 1000);
    }
}

// Run remaining countdown timer locally (1 second intervals)
setInterval(() => {
    leasesState.forEach(l => {
        if (l.remaining > 0) {
            l.remaining--;
            const macId = l.mac.replace(/:/g, '-');
            const el = document.getElementById(`expiry-${macId}`);
            if (el) {
                el.innerHTML = formatRemainingTime(l.remaining);
            }
        }
    });
}, 1000);

// Initialize on page load
(function() {
    const savedInterval = localStorage.getItem('dhcpleases_refresh_interval') || '10';
    const select = document.getElementById('auto-refresh-select');
    if (select) {
        select.value = savedInterval;
    }
    // Delay initial fetch slightly to let PJAX page transition finish,
    // ensuring the fetch request is not aborted by the browser.
    setTimeout(function() {
        if (savedInterval !== 'off') {
            changeAutoRefresh(savedInterval);
        } else {
            updateStatusAjax(false);
        }
    }, 100);
})();
</script>
JS_EOF

print "<div style='text-align: center; margin-top: 30px; font-size: 0.85em; color: #888;'>DHCP Leases Webmin Module v$version</div>\n";

&ui_print_footer("/", $text{'index'});
