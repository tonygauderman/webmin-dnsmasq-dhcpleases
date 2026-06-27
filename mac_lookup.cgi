#!/usr/bin/perl
# mac_lookup.cgi
# Resolves a MAC address prefix to a vendor name. Offline-first with online API fallback and local caching.

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

&ReadParse();
print "Content-type: application/json\n\n";

my $mac = lc($in{'mac'});
$mac =~ s/[^0-9a-f:]//g; # Sanitize

# Validate format
if ($mac !~ /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/) {
    print "{\"mac\":\"$mac\",\"vendor\":\"Unknown\"}\n";
    exit;
}

# 1. Check for Randomized / Locally Administered MAC addresses
# The 2nd hex digit of the 1st octet is 2, 6, a, or e.
my $sec = substr($mac, 1, 1);
if ($sec =~ /[26ae]/) {
    print "{\"mac\":\"$mac\",\"vendor\":\"Randomized / Private MAC\"}\n";
    exit;
}

my $oui = substr($mac, 0, 8); # First 3 bytes e.g. "00:11:22"

# 2. Built-in OUI Database for major tech/device manufacturers
my %oui_map = (
    '00:00:0c' => 'Cisco',
    '00:01:c0' => 'Compaq',
    '00:03:ff' => 'Microsoft (Hyper-V)',
    '00:05:69' => 'VMware',
    '00:0c:29' => 'VMware',
    '00:1c:14' => 'VMware',
    '00:50:56' => 'VMware',
    '00:0f:53' => 'Supermicro',
    '00:15:5d' => 'Microsoft (Hyper-V)',
    '00:16:3e' => 'Xen/LXC Virtual NIC',
    '52:54:00' => 'QEMU Virtual NIC',
    '00:1a:11' => 'Google',
    '00:1c:42' => 'Parallels Virtual NIC',
    '00:11:32' => 'Synology',
    '00:11:2f' => 'Dell',
    '00:1b:21' => 'Intel',
    '00:16:ea' => 'Intel',
    '00:26:82' => 'Intel',
    '00:17:88' => 'Philips Hue',
    '3c:5a:b4' => 'Google',
    '3c:a6:16' => 'Apple',
    'fc:ec:da' => 'Ubiquiti',
    'd8:07:b6' => 'Apple',
    'e4:e4:ab' => 'Apple',
    'b8:27:eb' => 'Raspberry Pi Foundation',
    'dc:a6:32' => 'Raspberry Pi Foundation',
    'e4:5f:01' => 'Raspberry Pi Foundation',
    '00:e0:4c' => 'Realtek',
    '00:22:15' => 'ASUSTek',
    '00:1f:c6' => 'ASUSTek',
    '00:19:21' => 'HP',
    '00:25:90' => 'Supermicro',
    '08:00:27' => 'VirtualBox NIC',
);

if (exists($oui_map{$oui})) {
    my $v = $oui_map{$oui};
    print "{\"mac\":\"$mac\",\"vendor\":\"" . &json_escape($v) . "\"}\n";
    exit;
}

# 3. Read persistent OUI cache file on the server
my $cache_dir = $module_config_directory || '/tmp';
my $cache_file = "$cache_dir/mac_vendor_cache";
my %cache;
if (-r $cache_file) {
    if (open(my $cfh, "<", $cache_file)) {
        while(my $line = <$cfh>) {
            $line =~ s/\r?\n//;
            my ($c_oui, $c_vendor) = split(/=/, $line, 2);
            if (defined($c_oui) && defined($c_vendor)) {
                $cache{$c_oui} = $c_vendor;
            }
        }
        close($cfh);
    }
}

if (exists($cache{$oui})) {
    print "{\"mac\":\"$mac\",\"vendor\":\"" . &json_escape($cache{$oui}) . "\"}\n";
    exit;
}

# 4. Fallback: Online API query (cache result if successful)
my $vendor = 'Unknown';
my $clean_oui = quotemeta($oui);
my $out = &backquote_command("curl -s --max-time 3 https://api.macvendors.com/$clean_oui 2>&1");
if ($? == 0 && $out !~ /error|too many/i && $out ne '' && length($out) < 100) {
    $vendor = $out;
    $vendor =~ s/^\s+//; $vendor =~ s/\s+$//;
    
    # Save to local persistent cache
    if (open(my $cfh, ">>", $cache_file)) {
        print $cfh "$oui=$vendor\n";
        close($cfh);
    }
}

print "{\"mac\":\"$mac\",\"vendor\":\"" . &json_escape($vendor) . "\"}\n";

sub json_escape {
    my ($s) = @_;
    return "" if (!defined($s));
    $s =~ s/\\/\\\\/g;
    $s =~ s/"/\\"/g;
    $s =~ s/\n/\\n/g;
    $s =~ s/\r/\\r/g;
    return $s;
}
