#!/usr/bin/perl
# save_reservation.cgi
# Creates a static DHCP reservation in the dnsmasq configuration

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

&ReadParse();
&error_setup($text{'save_err'});

my $mac = lc($in{'mac'});
my $ip = $in{'ip'};
my $hostname = $in{'hostname'};

# Sanitize and validate inputs
$mac =~ s/[^0-9a-f:]//g;
$ip =~ s/[^0-9\.]//g;

if (defined($hostname)) {
    $hostname =~ s/^\s+//; $hostname =~ s/\s+$//;
    if ($hostname eq 'undefined' || $hostname eq 'null' || $hostname =~ /^unnamed$/i || $hostname eq '') {
        $hostname = undef;
    } else {
        $hostname =~ s/[^a-zA-Z0-9\-\.]//g;
    }
}

if ($mac !~ /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/) {
    &error("Invalid MAC address: $mac");
}
if ($ip !~ /^\d+\.\d+\.\d+\.\d+$/) {
    &error("Invalid IP address: $ip");
}

# 1. Create static reservation in configuration
my ($ok, $type, $target) = &create_static_reservation($mac, $ip, $hostname);
if (!$ok) {
    &error($target); # contains error message
}

# 2. Reload or restart dnsmasq
if ($type eq 'hostsfile') {
    # If using hostsfile, a SIGHUP is enough to reload
    my ($reload_ok, $reload_err) = &service_action('reload');
    if (!$reload_ok) {
        # Fall back to restart if reload fails or isn't supported
        &service_action('restart');
    }
} else {
    # If appended to main config, a full restart is required
    my ($restart_ok, $restart_err) = &service_action('restart');
    if (!$restart_ok) {
        &error("Failed to restart dnsmasq: $restart_err");
    }
}

# 3. Redirect back to main page
&redirect("");
