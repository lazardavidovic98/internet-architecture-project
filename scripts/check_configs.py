"""Static checks for the exported Packet Tracer configurations.

Reads the running-configs in configs/as*/, the eBGP design in configs/bgp/,
the cabling table configs/links.csv and the host table configs/hosts.csv,
then checks the addressing and routing rules from the project assignment.

Usage:
    python scripts/check_configs.py

Exit code 0 means no errors (warnings are printed but do not fail the run).
Only the Python standard library is used.
"""

import csv
import ipaddress
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "configs"

IPV4_BLOCK = ipaddress.ip_network("55.8.0.0/16")
IPV6_BLOCK = ipaddress.ip_network("2001:33:EF08::/48")
MGMT_BLOCK = ipaddress.ip_network("192.168.0.0/24")

AS_NUMBERS = {"as10008": 10008, "as20008": 20008, "as30008": 30008, "as40008": 40008}
IGP = {10008: "ospf", 20008: "eigrp", 30008: "rip"}
# Routers that must stay out of the internal routing protocol (tasks 4 and 6).
STATIC_ONLY = {"R4", "R8"}
# Required host capacity per segment (task 1): hosts + 1 router interface.
LAN_HOSTS = 126
VLAN_HOSTS = 200


class Device:
    def __init__(self, name, asn):
        self.name = name
        self.asn = asn
        self.ipv4 = {}        # interface -> IPv4Interface
        self.ipv6 = {}        # interface -> [IPv6Interface]
        self.encap = {}       # subinterface -> VLAN id
        self.access = {}      # switch port -> VLAN id
        self.trunks = set()
        self.ospf = []        # (network, area)
        self.eigrp = []       # networks
        self.eigrp_v6 = []    # interfaces with "ipv6 eigrp"
        self.rip = []         # classful networks
        self.static = []      # (prefix, next hop)
        self.static_v6 = []
        self.redistribute = []


def wildcard_network(addr, wildcard):
    mask = ipaddress.ip_address(int(ipaddress.ip_address(wildcard)) ^ 0xFFFFFFFF)
    return ipaddress.ip_network(f"{addr}/{mask}", strict=False)


def parse_config(path, asn):
    dev = Device(path.stem, asn)
    section = None
    iface = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.startswith("!"):
            continue
        if not line.startswith(" "):
            iface = None
            section = line
            if line.startswith("interface "):
                iface = line.split()[1]
            elif line.startswith("ip route "):
                _, _, net, mask, hop = line.split()[:5]
                dev.static.append((ipaddress.ip_network(f"{net}/{mask}"), ipaddress.ip_address(hop)))
            elif line.startswith("ipv6 route "):
                _, _, net, hop = line.split()[:4]
                dev.static_v6.append((ipaddress.ip_network(net), ipaddress.ip_address(hop)))
            continue

        words = line.split()
        if iface:
            if words[:2] == ["ip", "address"] and len(words) >= 4:
                dev.ipv4[iface] = ipaddress.ip_interface(f"{words[2]}/{words[3]}")
            elif words[:2] == ["ipv6", "address"] and "link-local" not in words:
                dev.ipv6.setdefault(iface, []).append(ipaddress.ip_interface(words[2]))
            elif words[:2] == ["ipv6", "eigrp"]:
                dev.eigrp_v6.append(iface)
            elif words[:2] == ["encapsulation", "dot1Q"]:
                dev.encap[iface] = int(words[2])
            elif words[:3] == ["switchport", "access", "vlan"]:
                dev.access[iface] = int(words[3])
            elif words[:3] == ["switchport", "mode", "trunk"]:
                dev.trunks.add(iface)
        elif section.startswith("router ospf") and words[0] == "network":
            dev.ospf.append((wildcard_network(words[1], words[2]), int(words[4])))
        elif section.startswith("router eigrp") and words[0] == "network":
            wildcard = words[2] if len(words) > 2 else "0.0.0.255"
            dev.eigrp.append(wildcard_network(words[1], wildcard))
        elif section.startswith("router rip") and words[0] == "network":
            dev.rip.append(ipaddress.ip_network(words[1] + "/8"))
        if section and section.startswith(("router ", "ipv6 router ")) and words[0] == "redistribute":
            dev.redistribute.append(f"{section}: {' '.join(words)}")
    return dev


def load_devices():
    devices = {}
    for folder, asn in AS_NUMBERS.items():
        for path in sorted((CONFIGS / folder).glob("*.cfg")):
            devices[path.stem] = parse_config(path, asn)
    return devices


def load_bgp():
    """Return {router: (local AS, [(neighbor ip, remote AS, weight)], [networks])}."""
    bgp = {}
    for path in sorted((CONFIGS / "bgp").glob("*.cfg")):
        local, neighbors, networks = None, {}, []
        for line in path.read_text(encoding="utf-8").splitlines():
            words = line.split()
            if words[:2] == ["router", "bgp"]:
                local = int(words[2])
            elif words[:1] == ["neighbor"] and words[2] == "remote-as":
                neighbors.setdefault(words[1], {})["as"] = int(words[3])
            elif words[:1] == ["neighbor"] and words[2] == "weight":
                neighbors.setdefault(words[1], {})["weight"] = int(words[3])
            elif words[:1] == ["network"]:
                networks.append(ipaddress.ip_network(f"{words[1]}/{words[3]}"))
        bgp[path.stem] = (local, neighbors, networks)
    return bgp


def read_csv(name):
    with open(CONFIGS / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = 0

    def check(self, ok, message):
        if ok:
            self.passed += 1
        else:
            self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def check_addressing(devices, links, hosts, rep):
    # Every address is inside the assigned blocks.
    for dev in devices.values():
        for iface, addr in dev.ipv4.items():
            block = MGMT_BLOCK if iface.startswith("Vlan") else IPV4_BLOCK
            rep.check(addr in block, f"{dev.name} {iface} {addr} is outside {block}")
        for iface, addrs in dev.ipv6.items():
            rep.check(dev.asn == 20008, f"{dev.name} {iface} has IPv6 outside AS 20008")
            for addr in addrs:
                rep.check(addr.network.subnet_of(IPV6_BLOCK), f"{dev.name} {iface} {addr} is outside {IPV6_BLOCK}")

    # No duplicate addresses, and subnets of different segments never overlap.
    seen = {}
    subnets = {}
    for dev in devices.values():
        for iface, addr in dev.ipv4.items():
            who = f"{dev.name} {iface}"
            rep.check(addr.ip not in seen, f"duplicate address {addr.ip}: {who} and {seen.get(addr.ip)}")
            seen[addr.ip] = who
            subnets.setdefault(addr.network, []).append(who)
    for host in hosts:
        if host["ipv4"]:
            ip = ipaddress.ip_address(host["ipv4"])
            rep.check(ip not in seen, f"duplicate address {ip}: host {host['host']} and {seen.get(ip)}")
            seen[ip] = host["host"]
    nets = sorted(subnets, key=lambda n: (int(n.network_address), n.prefixlen))
    for i, a in enumerate(nets):
        for b in nets[i + 1:]:
            rep.check(not a.overlaps(b), f"overlapping subnets {a} ({subnets[a]}) and {b} ({subnets[b]})")

    # Both ends of every cable are in the same subnet.
    for link in links:
        a, b = devices.get(link["device_a"]), devices.get(link["device_b"])
        if not a or not b:
            continue  # host or switch access port, checked through hosts.csv
        pa, pb = link["port_a"], link["port_b"]
        if pa in a.ipv4 and pb in b.ipv4:
            rep.check(a.ipv4[pa].network == b.ipv4[pb].network,
                      f"link {a.name} {pa} - {b.name} {pb}: {a.ipv4[pa]} and {b.ipv4[pb]} are in different subnets")
            if link["cable"] == "serial":
                rep.check(a.ipv4[pa].network.prefixlen == 30, f"serial link {a.name}-{b.name} is not a /30")
        for v6a in a.ipv6.get(pa, []):
            for v6b in b.ipv6.get(pb, []):
                rep.check(v6a.network == v6b.network, f"link {a.name}-{b.name}: IPv6 {v6a} and {v6b} differ")

    # Subnet size covers the expected number of hosts (task 1).
    for dev in devices.values():
        for iface, addr in dev.ipv4.items():
            if addr.network.prefixlen == 30 or iface.startswith("Vlan"):
                continue
            need = VLAN_HOSTS if iface in dev.encap else LAN_HOSTS
            usable = addr.network.num_addresses - 2
            rep.check(usable >= need + 1, f"{dev.name} {iface} {addr.network}: {usable} usable < {need} hosts + gateway")

    # Hosts use their router as gateway and sit in the router's subnet.
    gateways = {addr.ip: (dev.name, iface, addr) for dev in devices.values() for iface, addr in dev.ipv4.items()}
    for host in hosts:
        if not host["ipv4"]:
            rep.warn(f"host '{host['host']}' ({host['segment']}) has no IP address configured")
            continue
        hip = ipaddress.ip_interface(f"{host['ipv4']}/{host['mask']}")
        gw = gateways.get(ipaddress.ip_address(host["gateway"]))
        rep.check(gw is not None, f"host {host['host']}: gateway {host['gateway']} is not a router address")
        if gw:
            rep.check(hip.ip in gw[2].network, f"host {host['host']} {hip.ip} is not in {gw[2].network}")
            if hip.network != gw[2].network:
                rep.warn(f"host {host['host']} uses mask /{hip.network.prefixlen}, router {gw[0]} {gw[1]} uses /{gw[2].network.prefixlen}")


def check_vlans(devices, rep):
    r5 = devices["R5"]
    rep.check(sorted(r5.encap.values()) == [10, 20], f"R5 routes VLANs {sorted(r5.encap.values())}, expected [10, 20]")
    rep.check(99 not in r5.encap.values(), "management VLAN 99 must not be routed by R5")
    for name in ("SW1", "SW2"):
        sw = devices[name]
        for port in range(1, 7):
            vlan = sw.access.get(f"FastEthernet0/{port}")
            rep.check(vlan == (10 if port <= 3 else 20), f"{name} Fa0/{port} is in VLAN {vlan}")
        rep.check("Vlan99" in sw.ipv4, f"{name} has no management address on VLAN 99")
    rep.check(devices["SW2"].access.get("FastEthernet0/15") == 99, "SW2 Fa0/15 must be in VLAN 99 (administrator)")


def covered(dev, addr):
    if IGP.get(dev.asn) == "ospf":
        return any(addr.ip in net for net, _ in dev.ospf)
    if IGP.get(dev.asn) == "eigrp":
        return any(addr.ip in net for net in dev.eigrp)
    if IGP.get(dev.asn) == "rip":
        return any(addr.ip in net for net in dev.rip)
    return False


def check_routing(devices, links, rep):
    neighbor_as = {}
    for link in links:
        a, b = devices.get(link["device_a"]), devices.get(link["device_b"])
        if a and b:
            neighbor_as[(a.name, link["port_a"])] = b.asn
            neighbor_as[(b.name, link["port_b"])] = a.asn

    for dev in devices.values():
        protocol = IGP.get(dev.asn)
        if dev.name in STATIC_ONLY:
            rep.check(not (dev.ospf or dev.eigrp or dev.rip), f"{dev.name} must not run an IGP")
            rep.check(bool(dev.static), f"{dev.name} has no static routes")
            continue
        if protocol is None or dev.name.startswith("SW"):
            continue
        # Every internal interface is advertised; links to other ASes and to static-only routers are not.
        for iface, addr in dev.ipv4.items():
            peer = neighbor_as.get((dev.name, iface))
            external = peer is not None and peer != dev.asn
            if external:
                if protocol != "rip":  # RIP uses a classful network statement, see the warning below
                    rep.check(not covered(dev, addr), f"{dev.name} {iface} faces another AS but is in {protocol}")
            else:
                rep.check(covered(dev, addr), f"{dev.name} {iface} {addr} is not advertised by {protocol}")
        if protocol == "rip":
            leaking = [i for i, a in dev.ipv4.items() if neighbor_as.get((dev.name, i), dev.asn) != dev.asn]
            if leaking:
                rep.warn(f"{dev.name}: 'network 55.0.0.0' also sends RIP updates out of inter-AS links {', '.join(leaking)} (no passive-interface)")
        if protocol == "eigrp" and dev.asn == 20008:
            for iface in dev.ipv6:
                rep.check(iface in dev.eigrp_v6, f"{dev.name} {iface} has IPv6 but no 'ipv6 eigrp 20008'")

    # Static routes point at directly connected next hops.
    for dev in devices.values():
        for prefix, hop in dev.static:
            rep.check(any(hop in a.network for a in dev.ipv4.values()), f"{dev.name} static {prefix} via {hop}: next hop not connected")
        for prefix, hop in dev.static_v6:
            rep.check(any(hop in a.network for addrs in dev.ipv6.values() for a in addrs),
                      f"{dev.name} IPv6 static {prefix} via {hop}: next hop not connected")

    # OSPF: three areas, backbone present, every non-backbone area touches an ABR.
    areas = {area for d in devices.values() for _, area in d.ospf}
    rep.check(areas == {0, 1, 2}, f"OSPF areas are {sorted(areas)}, expected [0, 1, 2]")
    for area in areas - {0}:
        abrs = [d.name for d in devices.values() if {a for _, a in d.ospf} >= {0, area}]
        rep.check(bool(abrs), f"OSPF area {area} has no ABR to area 0")

    # Routes towards the static-only routers are redistributed into the IGP.
    rep.check(any("redistribute static" in r and "ospf" in r for r in devices["R1"].redistribute), "R1 does not redistribute static into OSPF")
    for proto in ("router eigrp", "ipv6 router eigrp"):
        rep.check(any(r.startswith(proto) and "redistribute static" in r for r in devices["R7"].redistribute),
                  f"R7 does not redistribute static under '{proto}'")


def check_bgp(devices, bgp, rep):
    addr_owner = {a.ip: d for d in devices.values() for a in d.ipv4.values()}
    lan_routes = {a.network for d in devices.values() for i, a in d.ipv4.items()
                  if a.network.prefixlen < 30 and not i.startswith("Vlan")}
    advertised = set()
    for router, (local, neighbors, networks) in bgp.items():
        dev = devices[router]
        rep.check(local == dev.asn, f"BGP {router}: router bgp {local}, device is in AS {dev.asn}")
        for ip, opts in neighbors.items():
            peer = addr_owner.get(ipaddress.ip_address(ip))
            rep.check(peer is not None, f"BGP {router}: neighbor {ip} is not a router address")
            if peer:
                rep.check(opts.get("as") == peer.asn, f"BGP {router}: neighbor {ip} ({peer.name}) remote-as {opts.get('as')} != {peer.asn}")
                rep.check(any(ipaddress.ip_address(ip) in a.network for a in dev.ipv4.values()),
                          f"BGP {router}: neighbor {ip} is not directly connected")
                if router != "ISP":
                    want = 200 if peer.asn == 40008 else 100
                    rep.check(opts.get("weight") == want, f"BGP {router}: weight to {peer.name} is {opts.get('weight')}, expected {want}")
        for net in networks:
            rep.check(any(net.supernet_of(lan) for lan in lan_routes), f"BGP {router}: network {net} is not a LAN/VLAN")
            advertised |= {lan for lan in lan_routes if net.supernet_of(lan)}
    missing = sorted(lan_routes - advertised, key=lambda n: int(n.network_address))
    rep.check(not missing, f"LAN/VLAN networks not advertised in BGP: {', '.join(map(str, missing))}")


def main():
    devices = load_devices()
    links = read_csv("links.csv")
    hosts = read_csv("hosts.csv")
    bgp = load_bgp()
    rep = Report()

    check_addressing(devices, links, hosts, rep)
    check_vlans(devices, rep)
    check_routing(devices, links, rep)
    check_bgp(devices, bgp, rep)

    print(f"Devices: {len(devices)}  links: {len(links)}  hosts: {len(hosts)}  BGP routers: {len(bgp)}")
    print(f"Checks passed: {rep.passed}")
    for w in rep.warnings:
        print(f"WARNING  {w}")
    for e in rep.errors:
        print(f"ERROR    {e}")
    print("OK" if not rep.errors else f"FAILED ({len(rep.errors)} errors)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
