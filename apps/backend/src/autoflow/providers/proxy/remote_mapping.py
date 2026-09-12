"""Strict mapping of documented v1 controls; unknown values are never a success."""

import ipaddress
from dataclasses import replace
from typing import cast

from autoflow.domain.proxies.models import Capability
from autoflow.domain.proxies.remote import (
    Location,
    RemoteState,
    RotationMode,
    RotationSchedule,
)


def state(value: object) -> RemoteState:
    from .proxypanel import _object, _optional, _schema, parse_proxy

    body = _object(value)
    proxy = parse_proxy(body)
    bound = body.get("bound")
    available = body.get("rotation_available")
    if (
        bound is not None
        and type(bound) is not bool
        or available is not None
        and type(available) is not bool
    ):
        raise _schema()
    generation = body.get("location_generation", 0)
    if type(generation) is not int or generation < 0:
        raise _schema()
    current_ip = body.get("current_ip")
    try:
        current_ip = str(ipaddress.ip_address(current_ip)) if current_ip else None
    except (ValueError, TypeError):
        raise _schema() from None
    reason = body.get("rotation_blocked_reason")
    reasons = {
        "not_bound": "ProxyPanel 当前显示代理未绑定，暂不能更换 IP",
        "expired": "代理已到期",
        "paused": "代理已暂停",
        "cooldown": "ProxyPanel 当前处于换 IP 冷却期，请稍后刷新",
        "busy": "ProxyPanel 正在处理此代理，请稍后刷新",
    }
    active = proxy.remote_status == "active"
    general = None if active else "代理当前未处于有效状态"
    rotate_reason = general or (
        None
        if available is True
        else reasons.get(str(reason), "ProxyPanel 当前未允许此代理更换 IP，请刷新状态")
    )
    caps = (
        Capability(
            "change_ip",
            active and available is True,
            "confirmed-authenticated-doc",
            rotate_reason,
        ),
        Capability("relocate", active, "confirmed-authenticated-doc", general),
        Capability(
            "rotation_schedule",
            active,
            "confirmed-authenticated-doc",
            general,
            {"interval_minutes": [5, 10, 30, 60]},
        ),
    )
    return RemoteState(
        proxy,
        current_ip,
        generation,
        bound,
        _optional(_object(body.get("location", {})).get("country_code")),
        caps,
    )


def locations(value: object) -> list[Location]:
    from .proxypanel import _id, _object, _schema, _string

    body = _object(value)
    if not isinstance(body.get("locations"), list):
        raise _schema()
    result: dict[str, Location] = {}
    for item in body["locations"]:
        row = _object(item)
        city, country = _string(row.get("city")), _string(row.get("country"))
        carriers = row.get("carriers", [])
        if not isinstance(carriers, list):
            raise _schema()
        # Carrier-specific IDs are the authoritative targets. Fall back to the
        # city's ID only when the provider does not list carrier options.
        for child in carriers or [row]:
            child = _object(child)
            slots = child.get("available_slots")
            if type(slots) is not int or slots < 0:
                raise _schema()
            carrier = child.get("carrier")
            if carrier is not None:
                carrier = _string(carrier)
            location = Location(
                _id(child.get("location_id")), city, country, carrier, slots, (city,)
            )
            previous = result.get(location.id)
            if previous:
                # The live catalog lists multiple city aliases for a single
                # target ID. Keep that group explicit; do not promise an alias.
                if (previous.country, previous.carrier, previous.available_slots) != (
                    country,
                    carrier,
                    slots,
                ):
                    raise _schema()
                cities = tuple(sorted({*previous.cities, city}))
                location = replace(
                    previous,
                    cities=cities,
                    city=" / ".join(cities[:3])
                    + (f" 等 {len(cities)} 个城市" if len(cities) > 3 else ""),
                )
            result[location.id] = location
    return list(result.values())


def schedule(value: object) -> RotationSchedule:
    from .proxypanel import _object, _schema

    body = _object(value)
    if "schedule" not in body:
        raise _schema()
    if body["schedule"] is None:
        return RotationSchedule()
    item = _object(body["schedule"])
    mode, minutes = item.get("mode"), item.get("interval_minutes")
    if (
        mode not in ("same_city", "same_city_carriers", "full_pool")
        or type(minutes) is not int
        or not 1 <= minutes <= 60
    ):
        raise _schema()
    return RotationSchedule(True, cast(RotationMode, mode), minutes)
