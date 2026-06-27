# dnsmasq-dhcpleases-lib.pl
# Shared functions for dnsmasq DHCP Leases Webmin module

use WebminCore;
&init_config();

# get_dnsmasq_config()
# Parses the main dnsmasq config file and recursively imports conf-file and conf-dir files.
# Returns an array of hash references representing each configuration line.
sub get_dnsmasq_config {
    my $file = $_[0] || $config{'dnsmasq_conf'} || '/etc/dnsmasq.conf';
    my @rv;
    my %visited;
    &parse_dnsmasq_file($file, \@rv, \%visited);
    return \@rv;
}

# parse_dnsmasq_file(file, rv_arrayref, visited_href)
# Recursive helper to parse a configuration file.
sub parse_dnsmasq_file {
    my ($file, $rv, $visited) = @_;
    return if ($visited->{$file});
    $visited->{$file} = 1;
    
    if (!-r $file) {
        return;
    }
    open(my $fh, "<", $file) || return;
    my $line_no = 0;
    while(my $line = <$fh>) {
        $line =~ s/\r?\n//;
        my $orig = $line;
        
        # Split comment
        my $comment = "";
        if ($line =~ s/#(.*)$//) {
            $comment = $1;
            $comment =~ s/^\s+//;
            $comment =~ s/\s+$//;
        }
        
        # Trim leading/trailing whitespace
        my $trimmed = $line;
        $trimmed =~ s/^\s+//;
        $trimmed =~ s/\s+$//;
        
        my $item = {
            'file' => $file,
            'line' => $line_no,
            'orig' => $orig,
            'comment' => $comment,
            'type' => 'other',
            'value' => $trimmed
        };
        
        if ($trimmed eq '') {
            $item->{'type'} = 'empty';
        } elsif ($trimmed =~ /^dhcp-range\s*=\s*(.*)$/i) {
            $item->{'type'} = 'dhcp-range';
            $item->{'value'} = $1;
        } elsif ($trimmed =~ /^dhcp-host\s*=\s*(.*)$/i) {
            $item->{'type'} = 'dhcp-host';
            $item->{'value'} = $1;
        } elsif ($trimmed =~ /^dhcp-hostsfile\s*=\s*(.*)$/i) {
            $item->{'type'} = 'dhcp-hostsfile';
            $item->{'value'} = $1;
        } elsif ($trimmed =~ /^conf-file\s*=\s*(.*)$/i) {
            $item->{'type'} = 'conf-file';
            $item->{'value'} = $1;
        } elsif ($trimmed =~ /^conf-dir\s*=\s*(.*)$/i) {
            $item->{'type'} = 'conf-dir';
            $item->{'value'} = $1;
        }
        
        push(@$rv, $item);
        $line_no++;
        
        # Handle inclusions inline
        if ($item->{'type'} eq 'conf-file') {
            my $inc_file = $item->{'value'};
            # If relative path, assume relative to main directory (or just absolute)
            &parse_dnsmasq_file($inc_file, $rv, $visited);
        } elsif ($item->{'type'} eq 'conf-dir') {
            my $dir_spec = $item->{'value'};
            my ($dir, @exts) = split(/,/, $dir_spec);
            if (-d $dir && open(my $dh, $dir)) {
                my @files;
                while (my $f = readdir($dh)) {
                    next if ($f =~ /^\./ || $f =~ /~$/ || $f =~ /\.bak$/ || $f =~ /\.dpkg-[a-z]+$/);
                    my $full = "$dir/$f";
                    next if (!-f $full);
                    if (@exts) {
                        my $matched = 0;
                        foreach my $ext (@exts) {
                            if ($f =~ /\Q$ext\E$/) {
                                $matched = 1;
                                last;
                            }
                        }
                        next if (!$matched);
                    }
                    push(@files, $full);
                }
                closedir($dh);
                
                # Sort files to match dnsmasq load order
                foreach my $f (sort @files) {
                    &parse_dnsmasq_file($f, $rv, $visited);
                }
            }
        }
    }
    close($fh);
}

# parse_dhcp_host_string(str)
# Parses a comma-separated dhcp-host value into (mac, ip, hostname)
sub parse_dhcp_host_string {
    my ($str) = @_;
    my @parts = split(/,/, $str);
    my ($mac, $ip, $hostname);
    
    foreach my $p (@parts) {
        $p =~ s/^\s+//; $p =~ s/\s+$//;
        if ($p =~ /^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$/) {
            $mac = lc($p);
        } elsif ($p =~ /^\d+\.\d+\.\d+\.\d+$/) {
            $ip = $p;
        } elsif ($p =~ /^id:(\S+)/i) {
            # Client ID, skip or track if needed
        } elsif ($p ne 'ignore' && $p ne 'infinite' && $p !~ /^[0-9]+[smhd]$/) {
            # Treat other string as hostname
            $hostname = $p;
        }
    }
    return ($mac, $ip, $hostname);
}

# get_dhcp_leases()
# Parses dnsmasq.leases file. Returns an array of hashes.
sub get_dhcp_leases {
    my $file = $config{'leases_file'} || '/var/lib/misc/dnsmasq.leases';
    my @leases;
    if (!-r $file) {
        return \@leases;
    }
    open(my $fh, "<", $file) || return \@leases;
    while(my $line = <$fh>) {
        $line =~ s/\r?\n//;
        next if ($line =~ /^\s*$/);
        my ($expiry, $mac, $ip, $hostname, $client_id) = split(/\s+/, $line);
        $hostname = "" if ($hostname eq '*');
        $client_id = "" if ($client_id eq '*');
        
        push(@leases, {
            'expiry' => $expiry,
            'mac' => lc($mac),
            'ip' => $ip,
            'hostname' => $hostname,
            'client_id' => $client_id
        });
    }
    close($fh);
    return \@leases;
}

# get_dhcp_ranges(config_arrayref)
# Extracts configured dhcp-range IP blocks.
sub get_dhcp_ranges {
    my ($conf) = @_;
    my @ranges;
    foreach my $item (@$conf) {
        if ($item->{'type'} eq 'dhcp-range') {
            my $val = $item->{'value'};
            my @parts = split(/,/, $val);
            my ($start, $end);
            foreach my $p (@parts) {
                $p =~ s/^\s+//; $p =~ s/\s+$//;
                if ($p =~ /^\d+\.\d+\.\d+\.\d+$/) {
                    if (!defined($start)) {
                        $start = $p;
                    } elsif (!defined($end)) {
                        $end = $p;
                    }
                }
            }
            if (defined($start) && defined($end)) {
                push(@ranges, {
                    'start' => $start,
                    'end' => $end
                });
            }
        }
    }
    return \@ranges;
}

# get_static_reservations(config_arrayref)
# Parses dhcp-host entries inside dnsmasq configs and parses the dhcp-hostsfile if configured.
sub get_static_reservations {
    my ($conf) = @_;
    my @statics;
    
    # 1. Scan configuration files for dhcp-host options
    foreach my $item (@$conf) {
        if ($item->{'type'} eq 'dhcp-host') {
            my ($mac, $ip, $hostname) = &parse_dhcp_host_string($item->{'value'});
            push(@statics, {
                'mac' => $mac,
                'ip' => $ip,
                'hostname' => $hostname,
                'file' => $item->{'file'},
                'line' => $item->{'line'},
                'source' => 'config'
            });
        }
    }
    
    # 2. Check for configured dhcp-hostsfile(s)
    foreach my $item (@$conf) {
        if ($item->{'type'} eq 'dhcp-hostsfile') {
            my $file = $item->{'value'};
            if (-r $file && open(my $fh, "<", $file)) {
                my $line_no = 0;
                while (my $line = <$fh>) {
                    $line =~ s/\r?\n//;
                    if ($line =~ /^\s*$/ || $line =~ /^#/) {
                        $line_no++;
                        next;
                    }
                    my ($mac, $ip, $hostname) = &parse_dhcp_host_string($line);
                    push(@statics, {
                        'mac' => $mac,
                        'ip' => $ip,
                        'hostname' => $hostname,
                        'file' => $file,
                        'line' => $line_no,
                        'source' => 'hostsfile'
                    });
                    $line_no++;
                }
                close($fh);
            }
        }
    }
    
    return \@statics;
}

# ip_to_int(ip)
# Helper to convert IP address string to a 32-bit integer.
sub ip_to_int {
    my ($ip) = @_;
    my @parts = split(/\./, $ip);
    return ($parts[0] << 24) + ($parts[1] << 16) + ($parts[2] << 8) + $parts[3];
}

# get_pool_stats(ranges_ref, leases_ref)
# Calculates pool metrics.
sub get_pool_stats {
    my ($ranges, $leases) = @_;
    my $total_capacity = 0;
    my $active_leases_in_pool = 0;
    
    foreach my $r (@$ranges) {
        my $start_int = &ip_to_int($r->{'start'});
        my $end_int = &ip_to_int($r->{'end'});
        if ($end_int >= $start_int) {
            $total_capacity += ($end_int - $start_int + 1);
        }
    }
    
    foreach my $l (@$leases) {
        my $ip_int = &ip_to_int($l->{'ip'});
        my $in_pool = 0;
        foreach my $r (@$ranges) {
            my $start_int = &ip_to_int($r->{'start'});
            my $end_int = &ip_to_int($r->{'end'});
            if ($ip_int >= $start_int && $ip_int <= $end_int) {
                $in_pool = 1;
                last;
            }
        }
        if ($in_pool) {
            $active_leases_in_pool++;
        }
    }
    
    my $free_ips = $total_capacity - $active_leases_in_pool;
    $free_ips = 0 if ($free_ips < 0);
    
    my $utilization = 0;
    if ($total_capacity > 0) {
        $utilization = ($active_leases_in_pool / $total_capacity) * 100;
    }
    
    return {
        'total' => $total_capacity,
        'active' => $active_leases_in_pool,
        'free' => $free_ips,
        'utilization' => sprintf("%.1f", $utilization)
    };
}

# get_service_status()
# Checks systemd service active and boot-enabled status.
sub get_service_status {
    my $running = 0;
    my $enabled = 0;
    my $service = $config{'dnsmasq_service'} || 'dnsmasq';
    
    my $out = &backquote_command("systemctl is-active " . quotemeta($service) . " 2>&1");
    if ($out =~ /^active/i) {
        $running = 1;
    }
    
    my $boot_out = &backquote_command("systemctl is-enabled " . quotemeta($service) . " 2>&1");
    if ($boot_out =~ /^enabled/i) {
        $enabled = 1;
    }
    
    return ($running, $enabled);
}

# service_action(action)
# Performs standard systemd commands.
sub service_action {
    my ($action) = @_;
    my $service = $config{'dnsmasq_service'} || 'dnsmasq';
    my $cmd;
    if ($action eq 'start') {
        $cmd = "systemctl start " . quotemeta($service);
    } elsif ($action eq 'stop') {
        $cmd = "systemctl stop " . quotemeta($service);
    } elsif ($action eq 'restart') {
        $cmd = "systemctl restart " . quotemeta($service);
    } elsif ($action eq 'reload') {
        $cmd = "systemctl reload " . quotemeta($service);
    } elsif ($action eq 'enable') {
        $cmd = "systemctl enable " . quotemeta($service);
    } elsif ($action eq 'disable') {
        $cmd = "systemctl disable " . quotemeta($service);
    } else {
        return (0, "Invalid action");
    }
    my $out = &backquote_logged($cmd . " 2>&1");
    my $code = $?;
    return ($code == 0, $out);
}

# create_static_reservation(mac, ip, hostname)
# Pins a MAC to an IP. Prefers dhcp-hostsfile if configured, else appends to main config.
sub create_static_reservation {
    my ($mac, $ip, $hostname) = @_;
    my $conf = &get_dnsmasq_config();
    
    # Check if dhcp-hostsfile is configured
    my $hostsfile;
    foreach my $item (@$conf) {
        if ($item->{'type'} eq 'dhcp-hostsfile') {
            $hostsfile = $item->{'value'};
            last;
        }
    }
    
    if (defined($hostsfile)) {
        # Format: mac,ip[,hostname]
        my $line = "$mac,$ip";
        $line .= ",$hostname" if (defined($hostname) && $hostname ne '');
        
        # Append to hosts file
        open(my $fh, ">>", $hostsfile) || return (0, "Cannot write to hosts file: $hostsfile");
        print $fh $line . "\n";
        close($fh);
        return (1, "hostsfile", $hostsfile);
    } else {
        # Format: dhcp-host=mac,ip[,hostname]
        my $line = "dhcp-host=$mac,$ip";
        $line .= ",$hostname" if (defined($hostname) && $hostname ne '');
        
        my $main_conf = $config{'dnsmasq_conf'} || '/etc/dnsmasq.conf';
        open(my $fh, ">>", $main_conf) || return (0, "Cannot write to config file: $main_conf");
        print $fh $line . "\n";
        close($fh);
        return (1, "config", $main_conf);
    }
}

# remove_line_from_file(file, line_no)
# Helper to delete a specific line number (0-indexed) from a file.
sub remove_line_from_file {
    my ($file, $line_no) = @_;
    if (!-w $file) {
        return (0, "File is not writable");
    }
    open(my $fh, "<", $file) || return (0, "Cannot read file");
    my @lines = <$fh>;
    close($fh);
    
    open(my $out, ">", $file) || return (0, "Cannot write file");
    for (my $i = 0; $i < @lines; $i++) {
        next if ($i == $line_no);
        print $out $lines[$i];
    }
    close($out);
    return (1, "Success");
}

# delete_static_reservation(mac, ip)
# Deletes reservation from files.
sub delete_static_reservation {
    my ($mac, $ip) = @_;
    my $conf = &get_dnsmasq_config();
    my $statics = &get_static_reservations($conf);
    
    foreach my $s (@$statics) {
        # Match by MAC or IP
        if ((defined($mac) && lc($s->{'mac'}) eq lc($mac)) ||
            (defined($ip) && $s->{'ip'} eq $ip)) {
            my ($ok, $msg) = &remove_line_from_file($s->{'file'}, $s->{'line'});
            return ($ok, $msg);
        }
    }
    return (0, "Static reservation not found");
}

# delete_dhcp_lease(mac, ip)
# Deletes dynamic lease safely: stops service, edits lease file, starts service.
sub delete_dhcp_lease {
    my ($mac, $ip) = @_;
    my $leases_file = $config{'leases_file'} || '/var/lib/misc/dnsmasq.leases';
    
    # 1. Stop dnsmasq
    my ($stop_ok, $stop_err) = &service_action('stop');
    if (!$stop_ok) {
        return (0, "Failed to stop dnsmasq service: $stop_err");
    }
    
    # 2. Read leases, filter out match, write back
    my $ok = 0;
    if (-r $leases_file) {
        open(my $fh, "<", $leases_file);
        my @lines = <$fh>;
        close($fh);
        
        open(my $out, ">", $leases_file);
        foreach my $line (@lines) {
            my @cols = split(/\s+/, $line);
            if (@cols >= 3) {
                my $lmac = lc($cols[1]);
                my $lip = $cols[2];
                if ($lmac eq lc($mac) && $lip eq $ip) {
                    $ok = 1; # Found and skipped
                    next;
                }
            }
            print $out $line;
        }
        close($out);
    }
    
    # 3. Start dnsmasq
    my ($start_ok, $start_err) = &service_action('start');
    if (!$start_ok) {
        return (0, "Failed to start dnsmasq service: $start_err");
    }
    
    return ($ok, $ok ? "Success" : "Lease not found in leases file");
}

1;
