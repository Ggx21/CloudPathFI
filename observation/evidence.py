"""Model-specific evidence that an operator can record from an independent experiment."""

import math


MODEL_FIELDS = {
    "FM-01": ("controller_event", "flow_table"),
    "FM-02": ("route_table", "route_lookup"),
    "FM-03": ("security_group_rules", "security_group_audit_event"),
    "FM-04": ("configured_port", "listening_sockets"),
    "FM-05": ("tunnel_peer_config", "tunnel_endpoint_trace"),
    "FM-06": ("virtual_router_routes", "next_hop_trace"),
    "FM-07": ("ovs_port_counters", "packet_loss_pct"),
    "FM-08": ("rtt_ms", "one_way_delay_ms"),
    "FM-09": ("load_balancer_backends", "backend_health_event"),
    "FM-10": ("traffic_rate_pps", "queue_counters"),
    "FM-11": ("gateway_flow_table", "gateway_flow_trace"),
    "FM-12": ("physical_switch_event", "physical_switch_port_counters"),
    "FM-13": ("host_power_state", "power_controller_event"),
    "FM-14": ("optical_link_state", "optical_transceiver_event"),
    "FM-15": ("nic_driver_event", "nic_error_counters", "nic_link_state"),
}

ENUMS = {"host_power_state": ("on", "off", "transitioning", "unknown"),
         "optical_link_state": ("up", "down", "unknown"),
         "nic_link_state": ("up", "down", "unknown")}
NUMERIC = {"rtt_ms", "one_way_delay_ms", "traffic_rate_pps", "packet_loss_pct"}


def evidence_fields(model):
    if model not in MODEL_FIELDS:
        raise ValueError(f"unknown fault model: {model}")
    descriptions = {}
    for name in MODEL_FIELDS[model]:
        if name in ENUMS:
            descriptions[name] = " | ".join(ENUMS[name])
        elif name == "configured_port":
            descriptions[name] = "integer port from 0 to 65535"
        elif name in NUMERIC:
            descriptions[name] = "measured nonnegative number" if name != "packet_loss_pct" else "percentage from 0 to 100"
        else:
            descriptions[name] = "observed text or a structured JSON table/event"
    return descriptions


def check_evidence(model, evidence, required=False):
    fields = evidence_fields(model)
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object keyed by evidence name")
    matched = fields.keys() & evidence.keys()
    if required and not matched:
        raise ValueError(f"{model} needs during-phase evidence for at least one of: {', '.join(fields)}")
    for name in matched:
        value = evidence[name]
        if name in ENUMS:
            valid = value in ENUMS[name]
        elif name in NUMERIC:
            valid = type(value) in (int, float) and value >= 0 and math.isfinite(value)
            valid = valid and (name != "packet_loss_pct" or value <= 100)
        elif name == "configured_port":
            valid = type(value) is int and 0 <= value <= 65535
        else:
            valid = (isinstance(value, str) and value.strip()) or isinstance(value, (list, dict))
            if name.endswith(("_event", "_trace", "_counters")):
                valid = valid and bool(value)
        if not valid:
            raise ValueError(f"{name}: expected {fields[name]}")
