#!/usr/bin/perl
# delete_reservation.cgi
# Deletes a static DHCP reservation from config/hosts files.

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

&ReadParse();
&error_setup($text{'delete_res_err'});

my $mac = lc($in{'mac'});
my $ip = $in{'ip'};

# Sanitize
$mac =~ s/[^0-9a-f:]//g if ($mac);
$ip =~ s/[^0-9\.]//g if ($ip);

if (!$mac && !$ip) {
    &error("Missing MAC or IP parameter");
}

# 1. Check if hostsfile is in use before deleting, to decide action
my $conf = &get_dnsmasq_config();
my $has_hostsfile = 0;
foreach my $item (@$conf) {
    if ($item->{'type'} eq 'dhcp-hostsfile') {
        $has_hostsfile = 1;
        last;
    }
}

# 2. Delete static reservation
my ($ok, $msg) = &delete_static_reservation($mac, $ip);
if (!$ok) {
    &error($msg);
}

# 3. Reload or restart dnsmasq
if ($has_hostsfile) {
    my ($reload_ok, $reload_err) = &service_action('reload');
    if (!$reload_ok) {
        &service_action('restart');
    }
} else {
    my ($restart_ok, $restart_err) = &service_action('restart');
    if (!$restart_ok) {
        &error("Failed to restart dnsmasq: $restart_err");
    }
}

&redirect("");
