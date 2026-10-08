"""Benchmark projection quality under LiDAR-camera yaw calibration drift.

Example:
    python src/topic_a_yaw_sweep.py --data-root data/kitti_mini
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from starter.datasets import load_frame
from starter.projection import perturb_extrinsic, project_velo_to_image


def points_inside_boxes(uv: np.ndarray, boxes: list) -> np.ndarray:
    """Return a boolean mask for projected points inside any labeled 2D box."""
    if not boxes or len(uv) == 0:
        return np.zeros(len(uv), dtype=bool)
    result = np.zeros(len(uv), dtype=bool)
    for box in boxes:
        x1, y1, x2, y2 = box.bbox
        result |= (
            (uv[:, 0] >= x1)
            & (uv[:, 0] <= x2)
            & (uv[:, 1] >= y1)
            & (uv[:, 1] <= y2)
        )
    return result


def run_sweep(data_root: str, frames: list[str], yaw_values: list[float], out_csv: Path) -> list[dict]:
    rows: list[dict] = []
    for frame_id in frames:
        frame = load_frame(data_root, frame_id)
        n_points = len(frame["points"])
        for yaw_deg in yaw_values:
            calib = perturb_extrinsic(frame["calib"], yaw_deg=yaw_deg)
            uv, depth, mask = project_velo_to_image(frame["points"], calib, frame["image"].shape)
            in_box = points_inside_boxes(uv, frame["labels"])
            rows.append({
                "frame_id": frame_id,
                "yaw_deg": yaw_deg,
                "n_points": n_points,
                "n_labels": len(frame["labels"]),
                "inside_image_ratio": float(mask.mean()) if n_points else 0.0,
                "in_box_ratio_of_inside": float(in_box.mean()) if len(in_box) else 0.0,
                "in_box_ratio_of_all": float(in_box.sum() / n_points) if n_points else 0.0,
                "mean_depth_inside_m": float(depth.mean()) if len(depth) else float("nan"),
            })

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def plot_results(rows: list[dict], out_path: Path) -> None:
    yaw_values = sorted({row["yaw_deg"] for row in rows})
    mean_inside = [np.mean([r["inside_image_ratio"] for r in rows if r["yaw_deg"] == yaw]) for yaw in yaw_values]
    mean_in_box = [np.mean([r["in_box_ratio_of_all"] for r in rows if r["yaw_deg"] == yaw]) for yaw in yaw_values]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(yaw_values, mean_inside, marker="o")
    axes[0].set_title("Projected points inside image")
    axes[0].set_xlabel("Yaw drift (degrees)")
    axes[0].set_ylabel("Ratio of all LiDAR points")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(yaw_values, mean_in_box, marker="o", color="tab:red")
    axes[1].set_title("Points inside labeled 2D boxes")
    axes[1].set_xlabel("Yaw drift (degrees)")
    axes[1].set_ylabel("Ratio of all LiDAR points")
    axes[1].grid(True, alpha=0.3)

    fig.suptitle("Topic A: calibration yaw sweep")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data/kitti_mini")
    parser.add_argument("--frames", nargs="+", default=["000001", "000011", "000049"])
    parser.add_argument("--yaws", nargs="+", type=float, default=[0.0, 1.0, 2.0, 3.0])
    parser.add_argument("--out-csv", default="results/yaw_perturb_sweep.csv")
    parser.add_argument("--out-plot", default="results/figures/yaw_perturb_sweep.png")
    args = parser.parse_args()

    rows = run_sweep(args.data_root, args.frames, args.yaws, Path(args.out_csv))
    plot_results(rows, Path(args.out_plot))
    for yaw in args.yaws:
        values = [r["in_box_ratio_of_all"] for r in rows if r["yaw_deg"] == yaw]
        print(f"yaw={yaw:.1f} deg: mean_in_box_ratio={np.mean(values):.4%}")
    print(f"-> {args.out_csv}")
    print(f"-> {args.out_plot}")


if __name__ == "__main__":
    main()
