#!/usr/bin/perl
# status_ajax.cgi
# Returns DHCP leases, static reservations, pool stats, and service status in JSON format.

use WebminCore;
require './dnsmasq-dhcpleases-lib.pl';

&init_config();

# Print JSON headers
print "Content-type: application/json\n\n";

my ($running, $enabled) = &get_service_status();
my $leases = &get_dhcp_leases();
my $conf = &get_dnsmasq_config();
my $statics = &get_static_reservations($conf);
my $ranges = &get_dhcp_ranges($conf);
my $stats = &get_pool_stats($ranges, $leases);

# Escape strings helper for valid JSON
sub json_escape {
    my ($s) = @_;
    return "" if (!defined($s));
    $s =~ s/\\/\\\\/g;
    $s =~ s/"/\\"/g;
    $s =~ s/\n/\\n/g;
    $s =~ s/\r/\\r/g;
    $s =~ s/\t/\\t/g;
    return $s;
}

# Construct JSON manually to be 100% dependency-free
my $json = "{";
$json .= "\"running\":" . ($running ? "true" : "false") . ",";
$json .= "\"enabled\":" . ($enabled ? "true" : "false") . ",";

# Status HTML representation
my $status_html = $running ? 
    "<span style='color:green; font-weight:bold; font-size:1.1em;'>$text{'index_running'}</span>" :
    "<span style='color:red; font-weight:bold; font-size:1.1em;'>$text{'index_stopped'}</span>";
$json .= "\"status_html\":\"" . &json_escape($status_html) . "\",";

# Stats object
$json .= "\"stats\":{";
$json .= "\"total\":" . $stats->{'total'} . ",";
$json .= "\"active\":" . $stats->{'active'} . ",";
$json .= "\"free\":" . $stats->{'free'} . ",";
$json .= "\"utilization\":\"" . $stats->{'utilization'} . "\"";
$json .= "},";

# Leases array
$json .= "\"leases\":[";
my @lease_jsons;
my $time_now = time();
foreach my $l (@$leases) {
    # Check if this lease matches a static reservation
    my $is_static = 0;
    foreach my $s (@$statics) {
        if ((defined($s->{'mac'}) && lc($s->{'mac'}) eq lc($l->{'mac'})) ||
            (defined($s->{'ip'}) && $s->{'ip'} eq $l->{'ip'})) {
            $is_static = 1;
            last;
        }
    }
    my $type_str = $is_static ? "static" : "dynamic";
    my $remaining = $l->{'expiry'} - $time_now;
    $remaining = 0 if ($remaining < 0);
    
    my $ljson = "{";
    $ljson .= "\"expiry\":" . $l->{'expiry'} . ",";
    $ljson .= "\"remaining\":" . $remaining . ",";
    $ljson .= "\"mac\":\"" . &json_escape($l->{'mac'}) . "\",";
    $ljson .= "\"ip\":\"" . &json_escape($l->{'ip'}) . "\",";
    $ljson .= "\"hostname\":\"" . &json_escape($l->{'hostname'}) . "\",";
    $ljson .= "\"client_id\":\"" . &json_escape($l->{'client_id'}) . "\",";
    $ljson .= "\"type\":\"" . $type_str . "\"";
    $ljson .= "}";
    push(@lease_jsons, $ljson);
}
$json .= join(",", @lease_jsons);
$json .= "],";

# Statics array
$json .= "\"statics\":[";
my @static_jsons;
foreach my $s (@$statics) {
    my $sjson = "{";
    $sjson .= "\"mac\":\"" . &json_escape($s->{'mac'}) . "\",";
    $sjson .= "\"ip\":\"" . &json_escape($s->{'ip'}) . "\",";
    $sjson .= "\"hostname\":\"" . &json_escape($s->{'hostname'}) . "\",";
    $sjson .= "\"file\":\"" . &json_escape($s->{'file'}) . "\",";
    $sjson .= "\"line\":" . $s->{'line'} . ",";
    $sjson .= "\"source\":\"" . &json_escape($s->{'source'}) . "\"";
    $sjson .= "}";
    push(@static_jsons, $sjson);
}
$json .= join(",", @static_jsons);
$json .= "],";

# Ranges array
$json .= "\"ranges\":[";
my @range_jsons;
foreach my $r (@$ranges) {
    my $rjson = "{";
    $rjson .= "\"start\":\"" . &json_escape($r->{'start'}) . "\",";
    $rjson .= "\"end\":\"" . &json_escape($r->{'end'}) . "\"";
    $rjson .= "}";
    push(@range_jsons, $rjson);
}
$json .= join(",", @range_jsons);
$json .= "]";

$json .= "}";
print $json;
