#!/usr/bin/perl
# delete_lease.cgi
# Deletes an active dynamic DHCP lease from the leases file.

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

&ReadParse();
&error_setup($text{'delete_err'});

my $mac = lc($in{'mac'});
my $ip = $in{'ip'};

$mac =~ s/[^0-9a-f:]//g;
$ip =~ s/[^0-9\.]//g;

if (!$mac || !$ip) {
    &error("Missing MAC or IP parameter");
}

# 1. Execute dynamic lease deletion (handles service stop/start internally)
my ($ok, $msg) = &delete_dhcp_lease($mac, $ip);
if (!$ok) {
    &error($msg);
}

&redirect("");
