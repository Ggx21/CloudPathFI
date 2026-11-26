import math

def number(value, label, upper=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    if upper is not None and value > upper:
        raise ValueError(f"{label} must be at most {upper}")
    return value


def duration_fraction(metric):
    if "intervals" in metric:
        center = number(metric["baseline"], "baseline")
        radius = 2 * number(metric["baseline_sigma"], "baseline_sigma")
        outside = total = 0
        for duration, value in metric["intervals"]:
            total += number(duration, "interval duration")
            if abs(number(value, "measurement") - center) > radius:
                outside += duration
    else:
        total = number(metric["experiment_s"], "experiment_s")
        outside = number(metric["outside_2sigma_s"], "outside_2sigma_s", total)
    if total == 0:
        raise ValueError("experiment duration must be positive")
    return outside / total


def metric_impact(metric):
    if "normalized_degradation" in metric:
        nd = number(metric["normalized_degradation"], "normalized_degradation", 1)
    else:
        baseline = number(metric["baseline"], "baseline")
        observed = number(metric["observed"], "observed")
        direction = metric["direction"]
        if direction not in ("higher_is_worse", "lower_is_worse"):
            raise ValueError(f"unknown degradation direction: {direction}")
        scale = baseline or number(metric.get("scale", 0), "scale")
        if scale == 0:
            raise ValueError("supply a positive scale or normalized_degradation for a zero baseline")
        nd = (observed - baseline) / scale
        if direction == "lower_is_worse":
            nd = -nd
        nd = min(1, max(0, nd))
    ndur = duration_fraction(metric)
    score = number(metric["weight"], "metric weight") * nd * ndur
    return {"name": metric["name"], "ND": nd, "NDur": ndur, "contribution": score}
