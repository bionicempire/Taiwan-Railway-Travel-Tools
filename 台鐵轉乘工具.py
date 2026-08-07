import json as js
import re
import heapq
import traceback
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from data.site_name import TR_site_name as TR_sn
from data.route_length import TR_route_length as TR_rl
from data.class_name_map import class_name_map as cnm

"""------------只有這裡是可以改動的地方------------"""
waiting_time = 30
reverse_direction_transfer_time = 10
same_direction_transfer_time = 7
PATH = rf"C:\Huan_work\1-Taiwan Railway Travel Tools"
number_of_transfers = 1
station_tolerance = 0
show_fare_breakdown = False
"""----------------------------------------------"""
non_reserved_seat = {"1131", "1132", "1135"}
adj = {}
fare_tables: dict = {}


def init_dist_system():
    for segments in TR_rl.values():
        for segment in segments:
            s_ids = list(segment.keys())
            for i in range(len(s_ids)):
                if s_ids[i] not in adj:
                    adj[s_ids[i]] = []
                if i > 0:
                    d = abs(
                        Decimal(str(segment[s_ids[i]]))
                        - Decimal(str(segment[s_ids[i - 1]]))
                    )
                    adj[s_ids[i]].append((s_ids[i - 1], d))
                if i < len(s_ids) - 1:
                    d = abs(
                        Decimal(str(segment[s_ids[i]]))
                        - Decimal(str(segment[s_ids[i + 1]]))
                    )
                    adj[s_ids[i]].append((s_ids[i + 1], d))


def load_fare_table():
    global fare_tables
    categories = {
        "自強號": ["太魯閣", "普悠瑪", "新自強", "自強號"],
        "區間車": ["區間快", "區間車"],
        "莒光號": ["莒光號"],
    }
    for cat_name, file_keys in categories.items():
        path = rf"{PATH}\data\fare\{cat_name}里程票價表.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                records = js.load(f)
            table = {(r["start_code"], r["end_code"]): r for r in records}
            for fk in file_keys:
                for code in cnm.get(fk, set()):
                    fare_tables[code] = table
        except Exception as e:
            print(f"⚠ 無法載入{cat_name}票價表 {path}。原因：{e}")


def _lookup_fare(car_class, start_code, end_code):
    table = fare_tables.get(car_class)
    if not table:
        table = fare_tables.get("1131")
    if not table:
        return (
            Decimal("0"),
            Decimal("0"),
            f"[{get_sn_name(start_code)}-{get_sn_name(end_code)}:0]",
        )
    rec = table.get((start_code, end_code))
    if rec is None:
        rec = table.get((end_code, start_code))
    if rec is None:
        return (
            Decimal("0"),
            Decimal("0"),
            f"[{get_sn_name(start_code)}-{get_sn_name(end_code)}:0]",
        )
    return (
        Decimal(str(rec["fare"])),
        Decimal(str(rec.get("total_km", 0))),
        rec["formula"],
    )


def get_shortest_path(start, end):
    queue, distances = [(Decimal("0"), start, [start])], {start: Decimal("0")}
    while queue:
        dist, curr, path = heapq.heappop(queue)
        if curr == end:
            return path
        for neighbor, d in adj.get(curr, []):
            new_dist = dist + d
            if neighbor not in distances or new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                heapq.heappush(queue, (new_dist, neighbor, path + [neighbor]))
    return None


def calculate_total_fare(path):
    if not path:
        return Decimal("0"), Decimal("0"), ""
    merged_segments, i = [], 0
    while i < len(path):
        curr = path[i]
        if curr["class"] not in non_reserved_seat:
            merged_segments.append(curr)
            i += 1
        else:
            j = i
            while j < len(path) and path[j]["class"] in non_reserved_seat:
                j += 1
            merged_segments.append(
                {
                    "no": "+".join(path[k]["no"] for k in range(i, j)),
                    "class": curr["class"],
                    "from": path[i]["from"],
                    "to": path[j - 1]["to"],
                    "dep": path[i]["dep"],
                    "arr": path[j - 1]["arr"],
                }
            )
            i = j
    final_fares, final_kms, details = [], [], []
    for seg in merged_segments:
        val, km, t = _lookup_fare(seg["class"], seg["from"], seg["to"])
        final_fares.append(val)
        final_kms.append(km)
        details.append(t)
    total_val = sum(f for f in final_fares if f > 0)
    total_km_val = sum(k for k in final_kms if k > 0)
    meaningful_details = [d for d in details if not d.endswith(":0]")]
    if show_fare_breakdown and meaningful_details:
        formula = " + ".join(meaningful_details) + f" = {int(total_val)}"
    else:
        formula = str(int(total_val))
    return total_val, total_km_val, formula


def format_time(user_time):
    if not user_time or not user_time.strip():
        return None
    parts = re.split(r"[:：\.\s]+", user_time.strip())
    h, m, s = (
        parts[0].zfill(2),
        (parts[1].zfill(2) if len(parts) > 1 else "00"),
        (parts[2].zfill(2) if len(parts) > 2 else "00"),
    )
    return f"{h}:{m}:{s}"


def get_time_obj(t_str):
    h, m, s = map(int, t_str.split(":"))
    return datetime(2000, 1, 1) + timedelta(hours=h, minutes=m, seconds=s)


def time_obj_to_str(t_obj):
    base, total_secs = datetime(2000, 1, 1), int(
        (t_obj - datetime(2000, 1, 1)).total_seconds()
    )
    return f"{total_secs // 3600:02d}:{(total_secs % 3600) // 60:02d}:{total_secs % 60:02d}"


def normalize_arr_time(dep_time, arr_time):
    if arr_time < dep_time:
        h, m, s = map(int, arr_time.split(":"))
        return f"{h + 24:02d}:{m:02d}:{s:02d}"
    return arr_time


def time_diff_minutes(t1, t2):
    def to_min(ts):
        h, m, s = map(int, ts.split(":"))
        return h * 60 + m

    diff = to_min(t2) - to_min(t1)
    return diff + 1440 if diff < 0 else diff


def get_station_code(user_input):
    search_input = user_input.replace("台", "臺")
    for code, names in TR_sn.items():
        if (
            search_input == names[0]
            or user_input == code
            or search_input == names[1]
            or user_input == names[2]
        ):
            return code
    return user_input


def get_sn_name(code):
    return TR_sn.get(code, (code,))[1]


def get_car_type_name(car_class):
    return next((name for name, codes in cnm.items() if car_class in codes), "其他")


def get_valid_transfer_codes(start_code, end_code, tolerance):
    path = get_shortest_path(start_code, end_code)
    if not path:
        return None, set()
    valid = set(path)
    expanded = set()
    if tolerance > 0:
        frontier = {path[-1]}
        explored = set(path)
        for _ in range(tolerance):
            nxt = set()
            for node in frontier:
                for neighbor, _ in adj.get(node, []):
                    if neighbor not in explored:
                        nxt.add(neighbor)
                        explored.add(neighbor)
            valid.update(nxt)
            expanded.update(nxt)
            frontier = nxt
        frontier = {path[0]}
        explored = set(path)
        for _ in range(tolerance):
            nxt = set()
            for node in frontier:
                for neighbor, _ in adj.get(node, []):
                    if neighbor not in explored:
                        nxt.add(neighbor)
                        explored.add(neighbor)
            valid.update(nxt)
            expanded.update(nxt)
            frontier = nxt
    return valid, expanded


def is_same_direction(train1, train2, transfer_station):
    def get_route_and_direction(train, station):
        stops = train["stops"]
        try:
            idx = next(i for i, s in enumerate(stops) if s["id"] == station)
        except StopIteration:
            return None
        prev_stop = stops[idx - 1]["id"] if idx > 0 else None
        next_stop = stops[idx + 1]["id"] if idx < len(stops) - 1 else None
        if prev_stop is None or next_stop is None:
            return None
        for route_name, segments in TR_rl.items():
            route_dict = {}
            for seg in segments:
                route_dict.update(seg)
            if station not in route_dict:
                continue
            ordered = sorted(route_dict.keys(), key=lambda x: route_dict[x])
            try:
                st_idx = ordered.index(station)
            except ValueError:
                continue
            if (
                st_idx > 0
                and ordered[st_idx - 1] == prev_stop
                and st_idx < len(ordered) - 1
                and ordered[st_idx + 1] == next_stop
            ):
                return (route_name, "forward")
            if (
                st_idx > 0
                and ordered[st_idx - 1] == next_stop
                and st_idx < len(ordered) - 1
                and ordered[st_idx + 1] == prev_stop
            ):
                return (route_name, "backward")
        return None

    info1 = get_route_and_direction(train1, transfer_station)
    info2 = get_route_and_direction(train2, transfer_station)
    if info1 is not None and info2 is not None:
        route1, dir1 = info1
        route2, dir2 = info2
        return route1 == route2 and dir1 == dir2
    return False


def find_n_transfer_solutions(
    current_stn,
    end_stn,
    current_time,
    limit_dep_time,
    limit_arr_time,
    processed_trains,
    target_depth,
    path=[],
    used_trains=set(),
    current_depth=0,
    valid_transfer_codes=None,
    expanded_set=None,
    prev_train_full=None,
):
    results = []

    def get_dep(train):
        stop = next((s for s in train["stops"] if s["id"] == current_stn), None)
        return stop["dep"] if stop else "99:99:99"

    sorted_trains = sorted(processed_trains, key=get_dep)
    for t in sorted_trains:
        if t["no"] in used_trains:
            continue
        s_idx = next(
            (i for i, s in enumerate(t["stops"]) if s["id"] == current_stn), -1
        )
        if s_idx == -1:
            continue
        dep_time = t["stops"][s_idx]["dep"]
        if current_depth == 0:
            if not (current_time <= dep_time <= limit_dep_time):
                continue
        else:
            diff = time_diff_minutes(current_time, dep_time)
            if prev_train_full is not None:
                same_dir = is_same_direction(prev_train_full, t, current_stn)
            else:
                same_dir = False
            required_min = (
                same_direction_transfer_time
                if same_dir
                else reverse_direction_transfer_time
            )
            if not (required_min <= diff <= waiting_time):
                continue
        e_idx = next((i for i, s in enumerate(t["stops"]) if s["id"] == end_stn), -1)
        if current_depth == target_depth:
            if e_idx != -1 and e_idx > s_idx:
                eff_arr = normalize_arr_time(dep_time, t["stops"][e_idx]["arr"])
                if limit_arr_time and eff_arr > limit_arr_time:
                    continue
                full_path = path + [
                    {
                        "no": t["no"],
                        "class": t["class"],
                        "from": current_stn,
                        "to": end_stn,
                        "dep": dep_time,
                        "arr": eff_arr,
                    }
                ]
                val, km_val, formula = calculate_total_fare(full_path)
                has_expanded = False
                if expanded_set:
                    transfer_stations = set()
                    for seg in full_path:
                        if seg["from"] != full_path[0]["from"]:
                            transfer_stations.add(seg["from"])
                        if seg["to"] != full_path[-1]["to"]:
                            transfer_stations.add(seg["to"])
                    transfer_stations.discard(full_path[0]["from"])
                    transfer_stations.discard(full_path[-1]["to"])
                    if any(st in expanded_set for st in transfer_stations):
                        has_expanded = True
                results.append(
                    {
                        "path": full_path,
                        "total_fare": val,
                        "total_km": km_val,
                        "formula": formula,
                        "has_expanded": has_expanded,
                    }
                )
        elif current_depth < target_depth:
            for i in range(s_idx + 1, len(t["stops"])):
                trans_stn_id = t["stops"][i]["id"]
                if (
                    valid_transfer_codes is not None
                    and trans_stn_id not in valid_transfer_codes
                ):
                    continue
                arr_trans = normalize_arr_time(dep_time, t["stops"][i]["arr"])
                sub = find_n_transfer_solutions(
                    trans_stn_id,
                    end_stn,
                    arr_trans,
                    limit_dep_time,
                    limit_arr_time,
                    processed_trains,
                    target_depth,
                    path
                    + [
                        {
                            "no": t["no"],
                            "class": t["class"],
                            "from": current_stn,
                            "to": trans_stn_id,
                            "dep": dep_time,
                            "arr": arr_trans,
                        }
                    ],
                    used_trains | {t["no"]},
                    current_depth + 1,
                    valid_transfer_codes,
                    expanded_set,
                    prev_train_full=t,
                )
                if sub:
                    results.extend(sub)
    return results


def filter_best_transfer_stations(layer_results):
    groups = {}
    for res in layer_results:
        combo_key = "→".join([p["no"] for p in res["path"]])
        groups.setdefault(combo_key, []).append(res)

    final_results = []
    for combo, res_list in groups.items():
        all_non_reserved = all(
            seg["class"] in non_reserved_seat for res in res_list for seg in res["path"]
        )
        if all_non_reserved:
            best = min(res_list, key=lambda r: r["path"][-1]["arr"])
            best["same_combo"] = False
            final_results.append(best)
        else:
            if len(res_list) > 1:
                for res in res_list:
                    res["same_combo"] = True
            else:
                for res in res_list:
                    res["same_combo"] = False
            final_results.extend(res_list)
    return final_results


def find_waypoint_solutions(
    start_stn,
    end_stn,
    waypoint_set,
    current_time,
    limit_dep_time,
    limit_arr_time,
    processed_trains,
):
    results = []

    def get_stop_times(train, stn_id, base_dep):
        stop = next((s for s in train["stops"] if s["id"] == stn_id), None)
        if not stop:
            return None, None
        return normalize_arr_time(base_dep, stop["arr"]), normalize_arr_time(
            base_dep, stop["dep"]
        )

    def covered_between(train, from_stn, to_stn, required_set):
        stop_ids = [s["id"] for s in train["stops"]]
        try:
            f_idx, t_idx = stop_ids.index(from_stn), stop_ids.index(to_stn)
        except ValueError:
            return None
        if f_idx >= t_idx:
            return None
        covered = [sid for sid in stop_ids[f_idx + 1 : t_idx] if sid in required_set]
        if set(covered) != required_set:
            return None
        return f_idx, t_idx, covered

    for t in processed_trains:
        res = covered_between(t, start_stn, end_stn, waypoint_set)
        if res is None:
            continue
        s_idx, e_idx, wp_in_order = res
        base_dep = t["stops"][s_idx]["dep"]
        if not (current_time <= base_dep <= limit_dep_time):
            continue
        end_arr = normalize_arr_time(base_dep, t["stops"][e_idx]["arr"])
        if limit_arr_time and end_arr > limit_arr_time:
            continue
        all_stops = []
        s_arr, s_dep = get_stop_times(t, start_stn, base_dep)
        all_stops.append(
            {"code": start_stn, "arr": s_arr, "dep": s_dep, "is_transfer": False}
        )
        for wp in wp_in_order:
            arr, dep = get_stop_times(t, wp, base_dep)
            all_stops.append({"code": wp, "arr": arr, "dep": dep, "is_transfer": False})
        e_arr, e_dep = get_stop_times(t, end_stn, base_dep)
        all_stops.append(
            {"code": end_stn, "arr": e_arr, "dep": e_dep, "is_transfer": False}
        )
        full_path = [
            {
                "no": t["no"],
                "class": t["class"],
                "from": start_stn,
                "to": end_stn,
                "dep": base_dep,
                "arr": end_arr,
            }
        ]
        val, km_val, formula = calculate_total_fare(full_path)
        results.append(
            {
                "path": full_path,
                "total_fare": val,
                "total_km": km_val,
                "formula": formula,
                "all_stops": all_stops,
                "has_expanded": False,
            }
        )
    for t1 in processed_trains:
        stop_ids1 = [s["id"] for s in t1["stops"]]
        try:
            s1_idx = stop_ids1.index(start_stn)
        except ValueError:
            continue
        t1_dep = t1["stops"][s1_idx]["dep"]
        if not (current_time <= t1_dep <= limit_dep_time):
            continue
        for ti in range(s1_idx + 1, len(t1["stops"])):
            transfer_stn = stop_ids1[ti]
            if transfer_stn == end_stn:
                continue
            wp_in_t1 = [
                sid for sid in stop_ids1[s1_idx + 1 : ti] if sid in waypoint_set
            ]
            remaining_wp = waypoint_set - set(wp_in_t1)
            t1_arr = normalize_arr_time(t1_dep, t1["stops"][ti]["arr"])
            for t2 in processed_trains:
                if t1["no"] == t2["no"]:
                    continue
                res2 = covered_between(t2, transfer_stn, end_stn, remaining_wp)
                if res2 is None:
                    continue
                s2_idx, e2_idx, wp_in_t2 = res2
                t2_dep = t2["stops"][s2_idx]["dep"]
                t2_arr = normalize_arr_time(t2_dep, t2["stops"][e2_idx]["arr"])
                diff = time_diff_minutes(t1_arr, t2_dep)
                same_dir = is_same_direction(t1, t2, transfer_stn)
                required_min = (
                    same_direction_transfer_time
                    if same_dir
                    else reverse_direction_transfer_time
                )
                if not (required_min <= diff <= waiting_time):
                    continue
                if limit_arr_time and t2_arr > limit_arr_time:
                    continue
                all_stops = []
                s_arr, s_dep = get_stop_times(t1, start_stn, t1_dep)
                all_stops.append(
                    {
                        "code": start_stn,
                        "arr": s_arr,
                        "dep": s_dep,
                        "is_transfer": False,
                    }
                )
                for wp in wp_in_t1:
                    arr, dep = get_stop_times(t1, wp, t1_dep)
                    all_stops.append(
                        {"code": wp, "arr": arr, "dep": dep, "is_transfer": False}
                    )
                all_stops.append(
                    {
                        "code": transfer_stn,
                        "arr": t1_arr,
                        "dep": t2_dep,
                        "is_transfer": True,
                    }
                )
                for wp in wp_in_t2:
                    arr, dep = get_stop_times(t2, wp, t2_dep)
                    all_stops.append(
                        {"code": wp, "arr": arr, "dep": dep, "is_transfer": False}
                    )
                e_arr, e_dep = get_stop_times(t2, end_stn, t2_dep)
                all_stops.append(
                    {"code": end_stn, "arr": e_arr, "dep": e_dep, "is_transfer": False}
                )
                full_path = [
                    {
                        "no": t1["no"],
                        "class": t1["class"],
                        "from": start_stn,
                        "to": transfer_stn,
                        "dep": t1_dep,
                        "arr": t1_arr,
                    },
                    {
                        "no": t2["no"],
                        "class": t2["class"],
                        "from": transfer_stn,
                        "to": end_stn,
                        "dep": t2_dep,
                        "arr": t2_arr,
                    },
                ]
                val, km_val, formula = calculate_total_fare(full_path)
                results.append(
                    {
                        "path": full_path,
                        "total_fare": val,
                        "total_km": km_val,
                        "formula": formula,
                        "all_stops": all_stops,
                        "has_expanded": False,
                    }
                )
    return results


def get_next_date(date_str):
    return (datetime.strptime(date_str, "%Y%m%d") + timedelta(days=1)).strftime(
        "%Y%m%d"
    )


def add_24h(t_str):
    h, m, s = map(int, t_str.split(":"))
    return f"{h + 24:02d}:{m:02d}:{s:02d}"


def load_trains_from_file(file_path):
    no_pass = {"1104", "1112", "1150", "1130", "1106"}
    with open(file_path, "r", encoding="utf-8") as f:
        data = js.load(f)
    return [
        {
            "no": t.get("Train"),
            "class": str(t.get("CarClass", "")),
            "stops": [
                {
                    "id": s.get("Station"),
                    "arr": s.get("ARRTime"),
                    "dep": s.get("DEPTime"),
                }
                for s in t.get("TimeInfos", [])
            ],
        }
        for t in data.get("TrainInfos", [])
        if str(t.get("CarClass", "")) not in no_pass
    ]


def parse_date_input(raw):
    digits = re.sub(r"[-/\s]", "", raw.strip())
    if len(digits) <= 4:
        digits, today = digits.zfill(4), datetime.today()
        candidate = today.replace(month=int(digits[:2]), day=int(digits[2:]))
        if candidate.date() < today.date():
            candidate = candidate.replace(year=today.year + 1)
        return candidate.strftime("%Y%m%d")
    return digits


def build_output_filename(
    date_str, start_name, end_name, now_t_str, waypoint_names=None
):
    safe_time = now_t_str.replace(":", "") if now_t_str else "000000"
    if waypoint_names:
        wp_str = "_".join(waypoint_names)
        return f"查詢結果_{int(date_str)-19110000}_{start_name}_經{wp_str}_{end_name}_{safe_time}.txt"
    return f"查詢結果_{int(date_str)-19110000}_{start_name}_{end_name}_{safe_time}.txt"


if __name__ == "__main__":
    try:
        init_dist_system()
        load_fare_table()

        def _is_back(s):
            return s.strip() in ("!", "！")

        last_date = None
        last_start = None
        last_end = None
        last_waypoints_codes = None
        last_waypoints_names = None
        has_memory = False
        current_date, processed_trains = "", []
        while True:
            if has_memory and last_date and last_start and last_end is not None:
                current_date = last_date
                start_code = last_start
                end_code = last_end
                waypoint_codes = (
                    last_waypoints_codes if last_waypoints_codes is not None else []
                )
                waypoint_names = (
                    last_waypoints_names if last_waypoints_names is not None else []
                )
                step = 4
            else:
                step = 0
                start_code = end_code = None
                waypoint_codes, waypoint_names = [], []
            raw_time = None
            target_arr_time = limit_t_str = display_range = None
            sort_choice = "1"
            while True:
                if step == 0:
                    today_default = datetime.today().strftime("%m%d")
                    raw_date = input(
                        f"\n日期"
                        + (
                            f"，保持 [{current_date[4:6]}/{current_date[6:]}]: "
                            if current_date
                            else f"，本日 [{today_default}]: "
                        )
                    )
                    if raw_date.lower() == "exit":
                        step = -1
                        break
                    if _is_back(raw_date):
                        print("  ⚠ 已是第一個問題，無法再回退。")
                        continue
                    new_date = (
                        parse_date_input(raw_date)
                        if raw_date.strip()
                        else (
                            current_date
                            if current_date
                            else parse_date_input(today_default)
                        )
                    )
                    if not new_date:
                        continue
                    if new_date != current_date:
                        processed_trains, current_date = (
                            load_trains_from_file(rf"{PATH}\data\time\{new_date}.json"),
                            new_date,
                        )
                    last_date = current_date
                    step = 1
                elif step == 1:
                    raw = input("起站: ").strip()
                    if raw.lower() == "exit":
                        step = -1
                        break
                    if _is_back(raw):
                        has_memory = False
                        last_date = last_start = last_end = None
                        last_waypoints_codes = last_waypoints_names = None
                        step = 0
                        continue
                    if not raw:
                        print("  ⚠ 站名不可空白，請重新輸入。")
                        continue
                    code = get_station_code(raw)
                    if code not in TR_sn:
                        print(f"  ⚠ 找不到站名「{raw}」，請確認後重新輸入。")
                        continue
                    start_code = code
                    last_start = start_code
                    step = 2
                elif step == 2:
                    raw = input("終站: ").strip()
                    if raw.lower() == "exit":
                        step = -1
                        break
                    if _is_back(raw):
                        start_code = None
                        last_start = None
                        step = 1
                        continue
                    if not raw:
                        print("  ⚠ 站名不可空白，請重新輸入。")
                        continue
                    code = get_station_code(raw)
                    if code not in TR_sn:
                        print(f"  ⚠ 找不到站名「{raw}」，請確認後重新輸入。")
                        continue
                    if code == start_code:
                        print(f"  ⚠ 「{get_sn_name(code)}」與起站重複，請重新輸入。")
                        continue
                    end_code = code
                    last_end = end_code
                    step = 3
                elif step == 3:
                    raw_waypoints = input("中間必停站: ").strip()
                    if raw_waypoints.lower() == "exit":
                        step = -1
                        break
                    if _is_back(raw_waypoints):
                        end_code = None
                        last_end = None
                        waypoint_codes, waypoint_names = [], []
                        last_waypoints_codes = last_waypoints_names = None
                        step = 2
                        continue
                    if not raw_waypoints:
                        waypoint_codes, waypoint_names = [], []
                        last_waypoints_codes = []
                        last_waypoints_names = []
                        step = 4
                        continue
                    used_codes = {start_code, end_code}
                    temp_codes, temp_names, error = [], [], False
                    for w in raw_waypoints.split():
                        code = get_station_code(w.strip())
                        if code not in TR_sn:
                            print(f"  ⚠ 找不到站名「{w}」，請確認後重新輸入整行。")
                            error = True
                            break
                        if code in used_codes:
                            print(
                                f"  ⚠ 「{get_sn_name(code)}」與起站、終站或其他中間站重複，請重新輸入整行。"
                            )
                            error = True
                            break
                        used_codes.add(code)
                        temp_codes.append(code)
                        temp_names.append(get_sn_name(code))
                    if not error:
                        waypoint_codes, waypoint_names = temp_codes, temp_names
                        last_waypoints_codes = waypoint_codes
                        last_waypoints_names = waypoint_names
                        step = 4
                elif step == 4:
                    _utc8_now = datetime.now(timezone.utc) + timedelta(hours=8)
                    _default_time = _utc8_now.strftime("%H:%M:%S")
                    _raw = input(f"時間，現在時間 [{_default_time}]: ").strip()
                    if _is_back(_raw):
                        has_memory = False
                        last_date = last_start = last_end = None
                        last_waypoints_codes = last_waypoints_names = None
                        current_date = ""
                        processed_trains = []
                        step = 0
                        continue
                    raw_time = _raw if _raw else _default_time
                    has_memory = True
                    step = 5
                elif step == 5:
                    target_arr_input = input("希望抵達時間: ")
                    if _is_back(target_arr_input):
                        raw_time = None
                        target_arr_time = limit_t_str = display_range = (
                            limit_dep_t_str
                        ) = limit_arr_t_str = None
                        step = 4
                        continue
                    target_arr_time = format_time(target_arr_input)
                    if target_arr_time:
                        limit_t_str = limit_dep_t_str = limit_arr_t_str = "47:59:59"
                        display_range = (
                            f"至隔日 {target_arr_time} 前抵達"
                            if target_arr_time <= format_time(raw_time)
                            else f"於 {target_arr_time} 前抵達"
                        )
                    else:
                        limit_t_str = limit_dep_t_str = limit_arr_t_str = "47:59:59"
                        display_range = "全天"
                        try:
                            sh_input = input("查未來幾小時: ")
                            if _is_back(sh_input):
                                target_arr_time = limit_t_str = display_range = (
                                    limit_dep_t_str
                                ) = limit_arr_t_str = None
                                step = 5
                                continue
                            sh = float(sh_input or 0)
                            if sh > 0:
                                limit_dep_t_str = time_obj_to_str(
                                    get_time_obj(format_time(raw_time))
                                    + timedelta(hours=sh)
                                )
                                limit_arr_t_str = "47:59:59"
                                display_range = f"未來 {sh} 小時"
                        except:
                            pass
                    step = 6
                elif step == 6:
                    sort_raw = input(
                        "排序方式 (1:發車, 2:抵達, 3:票價, 4:時長): "
                    ).strip()
                    if _is_back(sort_raw):
                        target_arr_time = limit_t_str = display_range = None
                        sort_choice = "1"
                        step = 5
                        continue
                    sort_choice = sort_raw or "1"
                    break
            if step == -1:
                break
            station_tolerance = max(0, station_tolerance)
            try:
                max_transfers = (
                    int(number_of_transfers) if number_of_transfers is not None else 1
                )
                max_transfers = max(0, max_transfers)
            except ValueError:
                max_transfers = 2
            now_t_str = format_time(raw_time)
            _over_midnight_by_hours = (
                not target_arr_time and limit_dep_t_str and limit_dep_t_str > "24:00:00"
            )
            is_midnight, next_trains, limit_arr_today = (
                (bool(target_arr_time) and target_arr_time <= now_t_str)
                or _over_midnight_by_hours,
                [],
                None,
            )
            if is_midnight:
                if target_arr_time and target_arr_time <= now_t_str:
                    limit_arr_today = add_24h(target_arr_time)
                    display_range = f"至隔日 {target_arr_time} 前抵達"
                else:
                    limit_arr_today = "47:59:59"
                n_date = get_next_date(current_date)
                try:
                    next_trains = load_trains_from_file(
                        rf"{PATH}\data\time\{n_date}.json"
                    )
                except Exception as e:
                    print(f"⚠ 無法載入隔日（{n_date}）車次資料，原因：{e}")
            lines = []

            def out(text=""):
                print(text)
                lines.append(text)

            def method(x):
                if x == "1":
                    x = "依發車時間"
                elif x == "2":
                    x = "依抵達時間"
                elif x == "3":
                    x = "依票價遞增"
                elif x == "4":
                    x = "依時間長度遞增"
                return x

            wp_display = f" 經由：{'、'.join(waypoint_names)}" if waypoint_names else ""
            header = f"{'='*60}\n【搜尋】{get_sn_name(start_code)} -> {get_sn_name(end_code)}{wp_display} ({display_range})({method(sort_choice)})\n查詢日期：{current_date[:4]}/{current_date[4:6]}/{current_date[6:]} 查詢時間：{now_t_str}\n{'='*60}"
            out(header)
            if waypoint_codes:
                wp_set = set(waypoint_codes)
                wp_res = find_waypoint_solutions(
                    start_code,
                    end_code,
                    wp_set,
                    now_t_str,
                    limit_t_str if not is_midnight else "23:59:59",
                    (
                        limit_arr_today
                        if is_midnight
                        else (target_arr_time if target_arr_time else limit_t_str)
                    ),
                    processed_trains,
                )
                if is_midnight and next_trains:
                    _next_limit = (
                        target_arr_time
                        if target_arr_time
                        else (
                            limit_t_str
                            if not _over_midnight_by_hours
                            else time_obj_to_str(
                                get_time_obj(format_time(raw_time))
                                + timedelta(hours=sh)
                                - timedelta(days=1)
                            )
                        )
                    )
                    _next_arr_limit = target_arr_time if target_arr_time else "47:59:59"
                    wp_res_next = find_waypoint_solutions(
                        start_code,
                        end_code,
                        wp_set,
                        "00:00:00",
                        _next_limit,
                        _next_arr_limit,
                        next_trains,
                    )
                    if wp_res_next:
                        wp_res.extend(wp_res_next)
                if wp_res:
                    wp_res = [
                        res for res in wp_res if len(res["path"]) <= (max_transfers + 1)
                    ]
                    wp_res = filter_best_transfer_stations(wp_res)
                    if wp_res:
                        wp_res.sort(
                            key=lambda r: (
                                float(r["total_fare"])
                                if sort_choice == "3"
                                else (
                                    time_diff_minutes(
                                        r["path"][0]["dep"], r["path"][-1]["arr"]
                                    )
                                    if sort_choice == "4"
                                    else (
                                        lambda t: (int(t[:2]) * 60 + int(t[3:5]))
                                        + (1440 if t < now_t_str else 0)
                                    )(
                                        r["path"][-1]["arr"]
                                        if sort_choice == "2"
                                        else r["path"][0]["dep"]
                                    )
                                )
                            )
                        )
                    direct = [r for r in wp_res if len(r["path"]) == 1]
                    transfer1 = [r for r in wp_res if len(r["path"]) == 2]
                    wp_label = (
                        f"{get_sn_name(start_code)} 經 "
                        + "、".join(get_sn_name(c) for c in waypoint_codes)
                        + f" → {get_sn_name(end_code)}"
                    )
                    for group_label, group_data in [
                        ("直達", direct),
                        ("一次轉乘", transfer1),
                    ]:
                        if not group_data:
                            out(f"\n(無 {group_label} 方案 [{wp_label}])")
                            continue
                        out(
                            f"\n>>> 【{group_label}】方案 ({len(group_data)} 筆) [{wp_label}]：\n{'車次組合':^15} | 行程規劃\n"
                            + "-" * 140
                        )
                        combo_id_map = {}
                        next_id = 1
                        for res in group_data:
                            path, train_info = res["path"], [
                                f"{p['no'].rjust(4)}({get_car_type_name(p['class'])})"
                                for p in res["path"]
                            ]
                            all_stops = res.get("all_stops", [])
                            route_label = "→".join(
                                get_sn_name(s["code"]) for s in all_stops
                            )
                            detail = ""
                            for i, stop in enumerate(all_stops):
                                stn_name = get_sn_name(stop["code"])
                                if i == 0:
                                    detail = f"{stn_name} {stop['dep']}開"
                                elif i == len(all_stops) - 1:
                                    detail += f" -> {stn_name} {stop['arr']}抵"
                                else:
                                    if stop["is_transfer"]:
                                        detail += f" -> {stn_name}({stop['arr']}到/{stop['dep']}發)[轉]"
                                    else:
                                        detail += f" -> {stn_name}({stop['arr']}到/{stop['dep']}發)"
                            _dur = time_diff_minutes(
                                res["path"][0]["dep"], res["path"][-1]["arr"]
                            )
                            _dur_str = f"{_dur // 60}時{_dur % 60:02d}分"
                            if res.get("same_combo", False):
                                key = "→".join([p["no"] for p in res["path"]])
                                if key not in combo_id_map:
                                    combo_id_map[key] = next_id
                                    next_id += 1
                                prefix = f"[{combo_id_map[key]:02d}] "
                            else:
                                prefix = "    "
                            out(
                                f"{prefix}{'→'.join(train_info).center(15)} | [{route_label}] {detail} [時長: {_dur_str} | 里程: {res['total_km'].quantize(Decimal('0.1'))}km | 票價: {res['formula']}元]"
                            )
                else:
                    out("找不到符合條件且依序經過所有指定站點的方案。")
            else:
                vtc, expanded_set = get_valid_transfer_codes(
                    start_code, end_code, station_tolerance
                )
                for n in range(max_transfers + 1):
                    _vtc = vtc if n > 0 else None
                    _expanded = expanded_set if n > 0 else None
                    layer_res = find_n_transfer_solutions(
                        start_code,
                        end_code,
                        now_t_str,
                        limit_dep_t_str,
                        limit_arr_t_str,
                        processed_trains,
                        target_depth=n,
                        valid_transfer_codes=_vtc,
                        expanded_set=_expanded,
                    )
                    if is_midnight and next_trains:
                        _next_limit = (
                            target_arr_time
                            if target_arr_time
                            else (
                                limit_t_str
                                if not _over_midnight_by_hours
                                else time_obj_to_str(
                                    get_time_obj(format_time(raw_time))
                                    + timedelta(hours=sh)
                                    - timedelta(days=1)
                                )
                            )
                        )
                        _next_arr_limit = (
                            target_arr_time if target_arr_time else "47:59:59"
                        )
                        layer_res += find_n_transfer_solutions(
                            start_code,
                            end_code,
                            "00:00:00",
                            _next_limit,
                            _next_arr_limit,
                            next_trains,
                            target_depth=n,
                            valid_transfer_codes=_vtc,
                            expanded_set=_expanded,
                        )
                    filtered_layer_res = [
                        res for res in layer_res if len(res["path"]) == (n + 1)
                    ]
                    if filtered_layer_res:
                        final_list = filter_best_transfer_stations(filtered_layer_res)
                        final_list.sort(
                            key=lambda r: (
                                float(r["total_fare"])
                                if sort_choice == "3"
                                else (
                                    time_diff_minutes(
                                        r["path"][0]["dep"], r["path"][-1]["arr"]
                                    )
                                    if sort_choice == "4"
                                    else (
                                        lambda t: (int(t[:2]) * 60 + int(t[3:5]))
                                        + (1440 if t < now_t_str else 0)
                                    )(
                                        r["path"][-1]["arr"]
                                        if sort_choice == "2"
                                        else r["path"][0]["dep"]
                                    )
                                )
                            )
                        )
                        out(
                            f"\n>>> 【{'直達' if n==0 else f'轉乘 {n} 次'}】方案 ({len(final_list)} 筆)：\n{'車次組合':^15} | 行程規劃\n"
                            + "-" * 140
                        )
                        combo_id_map = {}
                        next_id = 1
                        for res in final_list:
                            path, train_info = res["path"], [
                                f"{p['no'].rjust(4)}({get_car_type_name(p['class'])})"
                                for p in res["path"]
                            ]
                            detail = (
                                f"{get_sn_name(path[0]['from'])} {path[0]['dep']}開"
                            )
                            for idx, step in enumerate(path):
                                to_stn = get_sn_name(step["to"])
                                if idx == len(path) - 1:
                                    detail += f" -> {to_stn} {step['arr']}抵"
                                else:
                                    detail += f" -> {to_stn}({step['arr']}到/{path[idx+1]['dep']}發)"
                            _dur = time_diff_minutes(
                                res["path"][0]["dep"], res["path"][-1]["arr"]
                            )
                            _dur_str = f"{_dur // 60}時{_dur % 60:02d}分"
                            warn = "⚠" if res.get("has_expanded", False) else ""
                            if res.get("same_combo", False):
                                key = "→".join([p["no"] for p in res["path"]])
                                if key not in combo_id_map:
                                    combo_id_map[key] = next_id
                                    next_id += 1
                                prefix = f"[{combo_id_map[key]:02d}]"
                            else:
                                prefix = "    "
                            out(
                                f"{prefix}{'→'.join(train_info).center(15)} | {detail} [時長: {_dur_str} | 里程: {res['total_km'].quantize(Decimal('0.1'))}km | 票價: {res['formula']}元]{warn}"
                            )
                    else:
                        out(f"\n(無 {'直達' if n==0 else f'轉乘 {n} 次'} 方案)")
            txt_filename = build_output_filename(
                current_date,
                get_sn_name(start_code),
                get_sn_name(end_code),
                now_t_str,
                waypoint_names if waypoint_codes else None,
            )
            output_path = rf"{PATH}\output\{txt_filename}"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"\n✔ 結果已儲存至：{output_path}")
    except Exception as e:
        print(f"系統錯誤: {e}")
        traceback.print_exc()
