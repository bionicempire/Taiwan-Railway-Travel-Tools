from decimal import Decimal, ROUND_HALF_UP
import heapq
import json
import time
from data.site_name import TR_site_name as TR_sn
from data.route_length import TR_route_length as TR_rl
from data.TR_fare_range import (
    fare_range as TR_fr,
    branches_fare as TR_bf,
)
from data.class_name_map import class_name_map as cnm

CAR_CLASSES = [
    ("1131", "區間車"),
    ("1111", "莒光號"),
    ("1103", "自強號"),
]
OUTPUT_DIR = r"C:\Huan_work\Taiwan Railway Travel Tools\data\fare"
_BRANCH_NAMES = {"平溪線", "深澳線", "六家線", "內灣線", "集集線", "沙崙線"}


def _build_branches():
    result = {}
    for name in _BRANCH_NAMES:
        if name in TR_rl:
            segs = TR_rl[name]
            br = {}
            for seg in segs:
                br.update(seg)
            result[name] = br
    return result


_BRANCHES = _build_branches()
station_db: dict = {}
adj: dict = {}


def _init():
    for route_name, segments in TR_rl.items():
        for segment in segments:
            for s_id, dist in segment.items():
                station_db.setdefault(s_id, {})[route_name] = Decimal(str(dist))
            s_ids = list(segment.keys())
            for i, sid in enumerate(s_ids):
                adj.setdefault(sid, [])
                if i > 0:
                    d = abs(
                        Decimal(str(segment[sid])) - Decimal(str(segment[s_ids[i - 1]]))
                    )
                    adj[sid].append((s_ids[i - 1], d))
                if i < len(s_ids) - 1:
                    d = abs(
                        Decimal(str(segment[sid])) - Decimal(str(segment[s_ids[i + 1]]))
                    )
                    adj[sid].append((s_ids[i + 1], d))


def _shortest_path(start: str, end: str) -> list[str] | None:
    queue = [(Decimal("0"), start, [start])]
    dist_map = {start: Decimal("0")}
    while queue:
        cost, curr, path = heapq.heappop(queue)
        if curr == end:
            return path
        for nb, d in adj.get(curr, []):
            nc = cost + d
            if nb not in dist_map or nc < dist_map[nb]:
                dist_map[nb] = nc
                heapq.heappush(queue, (nc, nb, path + [nb]))
    return None


def _get_pos(code: str) -> str:
    m = station_db.get(code, {}).get("西部幹線")
    if m is None:
        return "OTHER"
    return (
        "NORTH"
        if m <= Decimal("105.2")
        else ("SOUTH" if m >= Decimal("217.5") else "MS_ZONE")
    )


def get_trip_dist(start: str, end: str) -> Decimal:
    path = _shortest_path(start, end)
    if not path:
        return Decimal("0")
    ps, pe = _get_pos(start), _get_pos(end)
    if (ps == "NORTH" and pe == "SOUTH") or (ps == "SOUTH" and pe == "NORTH"):
        mode = "MOUNTAIN_ONLY"
    elif (ps in ["NORTH", "SOUTH"] and pe == "MS_ZONE") or (
        pe in ["NORTH", "SOUTH"] and ps == "MS_ZONE"
    ):
        mode = "SHORTEST"
    else:
        mode = "ACTUAL"
    total = Decimal("0")
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        routes = set(station_db[u]) & set(station_db[v])
        if (
            mode == "MOUNTAIN_ONLY"
            and "西部幹線 (海線)" in routes
            and "西部幹線" in routes
        ):
            route = "西部幹線"
        elif mode == "SHORTEST" and len(routes) > 1:
            route = min(routes, key=lambda r: abs(station_db[u][r] - station_db[v][r]))
        else:
            route = next(iter(routes))
        total += abs(station_db[u][route] - station_db[v][route])
    return total


def get_branch_info(stn: str):
    for name, br_data in _BRANCHES.items():
        if stn in br_data:
            return name, br_data
    return None, None


def get_all_branch_info(stn: str) -> list:
    return [(name, br_data) for name, br_data in _BRANCHES.items() if stn in br_data]


def get_mainline_junction(stn: str, visited: set = None) -> str | None:
    if visited is None:
        visited = set()
    if stn in visited:
        return None
    visited.add(stn)
    routes = station_db.get(stn, {})
    if any(r not in _BRANCH_NAMES for r in routes):
        return stn
    branches = get_all_branch_info(stn)
    if not branches:
        return None
    for name, br_data in branches:
        junc = min(br_data, key=lambda k: br_data[k])
        if junc == stn:
            for nb, _ in adj.get(stn, []):
                if nb not in visited:
                    res = get_mainline_junction(nb, visited)
                    if res:
                        return res
            continue
        upper = get_mainline_junction(junc, visited)
        if upper:
            return upper
    return None


def _sn(code) -> str:
    if not isinstance(code, str):
        return repr(code)
    entry = TR_sn.get(code)
    return entry[1] if entry and len(entry) > 1 else code


def _branch_fare(car_class: str, dist: Decimal, s: str, e: str) -> tuple[Decimal, str]:
    if dist < Decimal("10"):
        return _mainline_fare(car_class, dist, s, e, min10=False)
    dist_km = float(dist)
    f = Decimal(str(max(v for k, v in TR_bf.items() if k <= dist_km)))
    return f, f"[{_sn(s)}-{_sn(e)}:{int(f)}]"


def _mainline_fare(
    car_class: str, dist: Decimal, s: str, e: str, min10: bool = False
) -> tuple[Decimal, str]:
    rates = next(
        (r for c, r in TR_fr.items() if car_class in c), TR_fr[("1131", "1132", "1135")]
    )
    calc_dist = max(dist, Decimal("10")) if min10 else dist
    total, rem = Decimal("0"), calc_dist
    for thr in sorted(rates, reverse=True):
        if rem > thr:
            total += (rem - thr) * Decimal(str(rates[thr]))
            rem = Decimal(str(thr))
    f = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f, f"[{_sn(s)}-{_sn(e)}:{int(f)}]"


def calc_fare(
    car_class: str, start: str, end: str
) -> tuple[Decimal, str, Decimal, Decimal, Decimal]:
    total_dist = get_trip_dist(start, end)
    s_br, _ = get_branch_info(start)
    e_br, _ = get_branch_info(end)
    if total_dist < Decimal("10"):
        fare, formula = _mainline_fare(car_class, total_dist, start, end, min10=True)
        return fare, formula, total_dist, Decimal("0"), total_dist
    s_junc = get_mainline_junction(start) if s_br else None
    e_junc = get_mainline_junction(end) if e_br else None
    if s_junc == start:
        s_junc = None
    if e_junc == end:
        e_junc = None
    if s_junc and e_junc and s_junc != e_junc:
        d1 = get_trip_dist(start, s_junc)
        d2 = get_trip_dist(s_junc, e_junc)
        d3 = get_trip_dist(e_junc, end)
        v1, t1 = _branch_fare(car_class, d1, start, s_junc)
        v2, t2 = _mainline_fare(car_class, d2, s_junc, e_junc)
        v3, t3 = _branch_fare(car_class, d3, e_junc, end)
        total = v1 + v2 + v3
        parts = [t for t, v in [(t1, v1), (t2, v2), (t3, v3)] if v > 0]
        branch_km = d1 + d3
        mainline_km = d2
        return (
            total,
            " + ".join(parts),
            mainline_km,
            branch_km,
            branch_km + mainline_km,
        )
    if s_junc and e_junc and s_junc == e_junc:
        fare, formula = _branch_fare(car_class, total_dist, start, end)
        return fare, formula, Decimal("0"), total_dist, total_dist
    if s_junc and not e_junc:
        d1 = get_trip_dist(start, s_junc)
        d2 = get_trip_dist(s_junc, end)
        v1, t1 = _branch_fare(car_class, d1, start, s_junc)
        v2, t2 = _mainline_fare(car_class, d2, s_junc, end)
        total = v1 + v2
        parts = [t for t, v in [(t1, v1), (t2, v2)] if v > 0]
        branch_km = d1
        mainline_km = d2
        return (
            total,
            " + ".join(parts),
            mainline_km,
            branch_km,
            branch_km + mainline_km,
        )
    if not s_junc and e_junc:
        d1 = get_trip_dist(start, e_junc)
        d2 = get_trip_dist(e_junc, end)
        v1, t1 = _mainline_fare(car_class, d1, start, e_junc)
        v2, t2 = _branch_fare(car_class, d2, e_junc, end)
        total = v1 + v2
        parts = [t for t, v in [(t1, v1), (t2, v2)] if v > 0]
        mainline_km = d1
        branch_km = d2
        return (
            total,
            " + ".join(parts),
            mainline_km,
            branch_km,
            branch_km + mainline_km,
        )
    fare, formula = _mainline_fare(car_class, total_dist, start, end)
    return fare, formula, total_dist, Decimal("0"), total_dist


def run_for_car(car_class: str, car_name: str):
    _init()
    all_codes = sorted(TR_sn.keys())
    print(f"總站數：{len(all_codes)}　|　車種：{car_name} (車號 {car_class})")
    print("開始計算，站數多，需要一點時間，請耐心等候...")
    all_pairs = []
    t0 = time.time()
    total_rows = 0
    multi_rows = 0
    branch_rows = 0
    for si, start in enumerate(all_codes):
        for end in all_codes:
            if end == start:
                continue
            fare, formula, mainline_km, branch_km, total_km = calc_fare(
                car_class, start, end
            )
            is_branch = branch_km > 0
            if is_branch:
                branch_rows += 1
            if "] + [" in formula:
                multi_rows += 1
            all_pairs.append(
                {
                    "start_code": start,
                    # "start_name": _sn(start),
                    "end_code": end,
                    # "end_name": _sn(end),
                    # "mainline_km": float(mainline_km.quantize(Decimal("0.1"))),
                    # "branch_km": float(branch_km.quantize(Decimal("0.1"))),
                    "total_km": float(total_km.quantize(Decimal("0.1"))),
                    "fare": int(fare),
                    "formula": "{" + formula + "}",
                    # "via_branch": is_branch,
                }
            )
            total_rows += 1
        if (si + 1) % 20 == 0 or si == len(all_codes) - 1:
            print(f"  進度：{si + 1}/{len(all_codes)}　({time.time() - t0:.1f}s)")
    output_path = f"{OUTPUT_DIR}\\{car_name}里程票價表.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, ensure_ascii=False, indent=2)
    print("=" * 50)
    print("支線處理狀況總結：")
    print(f"  總筆數　　　　　　　　：{total_rows}")
    print(
        f"  有經過支線的筆數　　　：{branch_rows}　（{branch_rows / total_rows:.1%}）"
    )
    print(
        f"  純主線筆數　　　　　　：{total_rows - branch_rows}　（{(total_rows - branch_rows) / total_rows:.1%}）"
    )
    print(f"  幹支線組合計費　　　　：{multi_rows} 筆")
    print("=" * 50)
    print(f"已輸出 -> {output_path}")


def main():
    for car_class, car_name in CAR_CLASSES:
        run_for_car(car_class, car_name)
        print("\n")


if __name__ == "__main__":
    main()
