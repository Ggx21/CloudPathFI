"""Ordered paths from Table I and fault model names from Table II."""

PATHS = {
    "a": (
        "PM1.VM1.eth1", "PM1.VS1.tap1", "PM1.VS1.tap2", "PM1.VM2.eth1",
    ),
    "b": (
        "PM1.VM1.eth1", "PM1.VS1.tap1", "PM1.VS1.port1", "PM1.VR1.port1", "PM1.VR1.port2",
        "PM1.VS1.port2", "PM1.VS1.tap3", "PM1.VM3.eth1",
    ),
    "c": (
        "PM1.VM1.eth1", "PM1.VS1.tap1", "PM1.VS1.port1", "PM1.VR1.port1", "PM1.VR1.port2",
        "PM1.VS1.port2", "encapsulation", "PM1.VS1.tun1", "PM1.eth2", "PS1.port1",
        "PS1.port2", "PR1.port1", "PR1.port2", "PS3.port1", "PS3.port2", "PM3.eth2",
        "PM3.VS1.tun1", "decapsulation", "PM3.VS1.tap1", "PM3.VM5.eth1",
    ),
    "d": (
        "PM1.VM3.eth1", "PM1.VS1.tap3", "encapsulation", "PM1.VS1.tun1", "PM1.eth2",
        "PS1.port1", "PS1.port2", "PS2.port1", "PS2.port2", "PM2.eth2", "PM2.VS1.tun1",
        "decapsulation", "PM2.VS1.tap1", "PM2.VM4.eth1",
    ),
    "e": (
        "PM1.VM1.eth1", "PM1.VS1.tap1", "PM1.VS1.port1", "PM1.VR1.port1", "PM1.VR1.port3",
        "PM1.VR1.port2", "PM1.VR1.port1", "PM1.VS1.port3", "PM1.VS1.port4", "PM1.VS2.port1",
        "PM1.VS2.port2", "PM1.eth1", "PS1.port1", "PS1.port2", "PR1.port1", "PR1.port2",
        "PR2.port1", "PR2.port2", "Public Internet",
    ),
    "f": (
        "Container1.eth1", "VM1.VS1.veth1", "encapsulation", "VM1.VS1.tun1", "VM1.eth1",
        "PM1.VS1.tap1", "encapsulation", "PM1.VS1.tun1", "PM1.eth1", "PS1", "PR1", "PS2",
        "PM2.eth1", "PM2.VS1.tun1", "decapsulation", "PM2.VS1.tap1", "VM2.eth1",
        "VM2.VS1.tun1", "decapsulation", "VM2.VS1.veth1", "Container2.eth1",
    ),
}

FAULT_MODELS = {
    "FM-01": "SDN controller software fault",
    "FM-02": "VM routing misconfiguration",
    "FM-03": "Security group misconfiguration",
    "FM-04": "Component port misconfiguration",
    "FM-05": "VPC peer IP misconfiguration",
    "FM-06": "Virtual router error",
    "FM-07": "OVS bridge packet loss injection",
    "FM-08": "Network delay",
    "FM-09": "Load balancer misconfiguration",
    "FM-10": "Traffic burst congestion",
    "FM-11": "Gateway flow table error",
    "FM-12": "Physical switch error",
    "FM-13": "Physical host power outage",
    "FM-14": "Fiber link disconnection",
    "FM-15": "NIC hardware failure",
}
