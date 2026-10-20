from compliance import check_station_compliance
from engineering import write_ncr_report
from inspection import classify_operator_remark, decide_disposition, parse_sensor_lines
from plant_config import LOG_FILE


def main(rejects: list[dict], station_reports: dict[str, str]):
    rows = parse_sensor_lines(LOG_FILE)
    print(f"parsed {len(rows)} sensor rows")
    for r in rejects:
        defect = classify_operator_remark(r["remark"])
        disp = decide_disposition(r["measurements"])
        print(write_ncr_report(r["part"], r["lot"], disp, f"{defect}: {r['remark']}"))
    print(check_station_compliance(station_reports))
