#!/usr/bin/perl
# action.cgi
# Starts, stops, restarts, or enables/disables the dnsmasq service at boot.

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

&ReadParse();
&error_setup($text{'action_err'});

# 1. Handle boot status
my $want_boot = $in{'boot'} ? 'enable' : 'disable';
my ($boot_ok, $boot_err) = &service_action($want_boot);
if (!$boot_ok) {
    &error($text{'action_boot_err'} . ": " . $boot_err);
}

# 2. Handle service actions (start, stop, restart)
my $action;
if (defined($in{'start'})) { $action = 'start'; }
elsif (defined($in{'stop'})) { $action = 'stop'; }
elsif (defined($in{'restart'})) { $action = 'restart'; }
else { $action = $in{'action'}; }

if (defined($action) && $action ne '') {
    my ($action_ok, $action_err) = &service_action($action);
    if (!$action_ok) {
        &error($text{'action_err'} . ": " . $action_err);
    }
}

&redirect("");
