#!/usr/bin/perl
# test_parser.pl
# Unit test for dnsmasq DHCP Leases configuration parser and pool statistics.

use strict;
use warnings;
use File::Basename;
use File::Spec;

my $script_dir = dirname(File::Spec->rel2abs(__FILE__));

# 1. Create mock web-lib.pl and WebminCore.pm so ntpsec-style test runner works
my $mock_web_lib = File::Spec->catfile($script_dir, 'web-lib.pl');
my $mock_core_lib = File::Spec->catfile($script_dir, 'WebminCore.pm');

open(my $fh, ">", $mock_web_lib) or die "Failed to create mock web-lib.pl: $!";
print $fh <<'EOF';
# Mock web-lib.pl for testing
package main;

our %config = (
    'dnsmasq_conf' => 'test_dnsmasq.conf',
    'leases_file' => 'test_leases',
    'dnsmasq_service' => 'dnsmasq'
);
our %text = (
    'save_err' => 'Failed to save reservation',
    'delete_err' => 'Failed to delete lease',
    'delete_res_err' => 'Failed to delete reservation'
);
our $module_config_directory = '.';

sub init_config { }
sub lock_file { }
sub unlock_file { }

# Mock commands output
our $mock_systemctl_active = "active\n";
our $mock_systemctl_enabled = "enabled\n";
our @logged_commands;

sub backquote_command {
    my ($cmd) = @_;
    $? = 0;
    if ($cmd =~ /is-active/) {
        return $mock_systemctl_active;
    } elsif ($cmd =~ /is-enabled/) {
        return $mock_systemctl_enabled;
    }
    return "";
}

sub backquote_logged {
    my ($cmd) = @_;
    push(@logged_commands, $cmd);
    $? = 0;
    return "Command executed successfully";
}
1;
EOF
close($fh);

open(my $cfh_core, ">", $mock_core_lib) or die "Failed to create mock WebminCore.pm: $!";
print $cfh_core <<"EOF";
package WebminCore;
sub import {
    my \$caller = caller;
    do "$mock_web_lib";
    no strict 'refs';
    *{"\${caller}::init_config"} = \\&main::init_config;
    *{"\${caller}::backquote_command"} = \\&main::backquote_command;
    *{"\${caller}::backquote_logged"} = \\&main::backquote_logged;
}
1;
EOF
close($cfh_core);

# 2. Setup mock configuration and lease files
my $test_conf = 'test_dnsmasq.conf';
open(my $conf_fh, ">", $test_conf) or die "Failed to create test config file: $!";
print $conf_fh <<'EOF';
# Main dnsmasq.conf for test
interface=eth0
dhcp-range=192.168.10.50,192.168.10.150,12h
dhcp-range=192.168.20.100,192.168.20.110,24h
dhcp-range=10.0.0.10,10.0.0.200,255.255.0.0,8h
dhcp-host=00:11:22:33:44:55,192.168.10.60,test-laptop
dhcp-hostsfile=test_hostsfile
conf-file=test_extra.conf
EOF
close($conf_fh);

my $test_extra = 'test_extra.conf';
open(my $extra_fh, ">", $test_extra) or die "Failed to create test extra config: $!";
print $extra_fh <<'EOF';
# Extra config file included recursively
dhcp-host=66:77:88:99:aa:bb,192.168.10.80,extra-pc
EOF
close($extra_fh);

my $test_hostsfile = 'test_hostsfile';
open(my $hosts_fh, ">", $test_hostsfile) or die "Failed to create test hostsfile: $!";
print $hosts_fh <<'EOF';
# Custom hosts file containing static maps
00:aa:bb:cc:dd:ee,192.168.10.90,hostsfile-printer
EOF
close($hosts_fh);

my $test_leases = 'test_leases';
open(my $leases_fh, ">", $test_leases) or die "Failed to create test leases: $!";
my $future_time = time() + 3600;
print $leases_fh <<EOF;
$future_time 00:11:22:33:44:55 192.168.10.60 test-laptop 01:00:11:22:33:44:55
$future_time 00:22:33:44:55:66 192.168.10.70 test-phone *
EOF
close($leases_fh);

# 3. Load library and perform assertions
push(@INC, $script_dir);
require './dnsmasq-dhcpleases-lib.pl';

print "--- Testing Config Parser ---\n";
my $config_lines = &get_dnsmasq_config($test_conf);
print "Parsed " . scalar(@$config_lines) . " lines recursively.\n";
die "Recursive parsing failed to parse enough lines" if (scalar(@$config_lines) < 6);

# Verify config ranges
my $ranges = &get_dhcp_ranges($config_lines);
die "Expected 3 DHCP ranges, got " . scalar(@$ranges) if (scalar(@$ranges) != 3);
die "Range 1 start mismatch" if ($ranges->[0]->{'start'} ne '192.168.10.50');
die "Range 1 end mismatch" if ($ranges->[0]->{'end'} ne '192.168.10.150');
die "Range 1 netmask mismatch" if ($ranges->[0]->{'netmask'} ne '255.255.255.0');
die "Range 2 start mismatch" if ($ranges->[1]->{'start'} ne '192.168.20.100');
die "Range 2 end mismatch" if ($ranges->[1]->{'end'} ne '192.168.20.110');
die "Range 2 netmask mismatch" if ($ranges->[1]->{'netmask'} ne '255.255.255.0');
die "Range 3 start mismatch" if ($ranges->[2]->{'start'} ne '10.0.0.10');
die "Range 3 end mismatch" if ($ranges->[2]->{'end'} ne '10.0.0.200');
die "Range 3 netmask mismatch" if ($ranges->[2]->{'netmask'} ne '255.255.0.0');
print "Ranges parsed successfully!\n";

# Verify static reservations (including configuration files and separate hostsfile)
my $statics = &get_static_reservations($config_lines);
die "Expected 3 static reservations, got " . scalar(@$statics) if (scalar(@$statics) != 3);

# Verify individual statics
my %statics_map = map { $_->{'mac'} => $_ } @$statics;
die "Missing static reservation from main conf" if (!$statics_map{'00:11:22:33:44:55'});
die "IP mismatch for main conf static" if ($statics_map{'00:11:22:33:44:55'}->{'ip'} ne '192.168.10.60');
die "Hostname mismatch for main conf static" if ($statics_map{'00:11:22:33:44:55'}->{'hostname'} ne 'test-laptop');

die "Missing static reservation from extra conf" if (!$statics_map{'66:77:88:99:aa:bb'});
die "IP mismatch for extra conf static" if ($statics_map{'66:77:88:99:aa:bb'}->{'ip'} ne '192.168.10.80');

die "Missing static reservation from hostsfile" if (!$statics_map{'00:aa:bb:cc:dd:ee'});
die "IP mismatch for hostsfile static" if ($statics_map{'00:aa:bb:cc:dd:ee'}->{'ip'} ne '192.168.10.90');
die "Source mismatch for hostsfile static" if ($statics_map{'00:aa:bb:cc:dd:ee'}->{'source'} ne 'hostsfile');
print "Static reservations parsed successfully!\n";

# Verify dynamic leases
print "--- Testing Leases Parser ---\n";
my $leases = &get_dhcp_leases();
die "Expected 2 leases, got " . scalar(@$leases) if (scalar(@$leases) != 2);
die "Lease 1 IP mismatch" if ($leases->[0]->{'ip'} ne '192.168.10.60');
die "Lease 2 MAC mismatch" if ($leases->[1]->{'mac'} ne '00:22:33:44:55:66');
print "Leases parsed successfully!\n";

# Verify pool statistics calculations
print "--- Testing Pool Utilization Calculations ---\n";
my $stats = &get_pool_stats($ranges, $leases);
# Pool 1 range: 192.168.10.50 - 150 = 101 IPs
# Pool 2 range: 192.168.20.100 - 110 = 11 IPs
# Pool 3 range: 10.0.0.10 - 200 = 191 IPs
# Total pool capacity = 101 + 11 + 191 = 303 IPs
# Leases:
# - 192.168.10.60 (falls in Range 1) -> 1 active lease in pool
# - 192.168.10.70 (falls in Range 1) -> 2 active leases in pool
# Total active leases in pool = 2
# Free IPs = 303 - 2 = 301
# Utilization = (2 / 303) * 100 = 0.66% -> formatted as "0.7"
die "Total capacity calculation mismatch (expected 303, got $stats->{total})" if ($stats->{'total'} != 303);
die "Active leases calculation mismatch (expected 2, got $stats->{active})" if ($stats->{'active'} != 2);
die "Free IPs calculation mismatch (expected 301, got $stats->{free})" if ($stats->{'free'} != 301);
die "Utilization percentage mismatch (expected 0.7, got $stats->{utilization})" if ($stats->{'utilization'} ne '0.7');
print "Pool stats verified successfully!\n";

# Verify promotion creation (One-click reservation)
print "--- Testing Reservation Creation ---\n";
# Should append to hostsfile since 'test_hostsfile' is configured
my ($create_ok, $create_type, $create_target) = &create_static_reservation("11:22:33:44:55:66", "192.168.10.120", "new-reserved");
die "Create reservation failed" if (!$create_ok);
die "Expected creation in hostsfile, got: $create_type" if ($create_type ne 'hostsfile');

# Check that the file actually contains the new reservation
open(my $check_fh, "<", $create_target) or die "Cannot open check hostsfile: $!";
my $file_content = do { local $/; <$check_fh> };
close($check_fh);
die "Hostsfile did not receive new line: $file_content" if ($file_content !~ /11:22:33:44:55:66,192.168.10.120,new-reserved/);
print "Static reservation successfully added!\n";

# Verify deletion of reservation
print "--- Testing Reservation Deletion ---\n";
my ($delete_ok, $delete_msg) = &delete_static_reservation("11:22:33:44:55:66", "192.168.10.120");
die "Delete reservation failed: $delete_msg" if (!$delete_ok);

# Check that the line is gone
open(my $check_fh2, "<", $create_target) or die "Cannot open check hostsfile: $!";
my $file_content2 = do { local $/; <$check_fh2> };
close($check_fh2);
die "Hostsfile still contains deleted reservation: $file_content2" if ($file_content2 =~ /11:22:33:44:55:66,192.168.10.120,new-reserved/);
print "Static reservation successfully deleted!\n";

# Clean up mock files
unlink($test_conf, $test_extra, $test_hostsfile, $test_leases, $mock_web_lib, $mock_core_lib);
print "\nAll tests passed successfully!\n";
exit 0;
