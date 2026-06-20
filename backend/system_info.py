# -*- coding: utf-8 -*-
"""Thu thập thông tin phần cứng / hệ thống cho Tab 1."""

import platform
import socket

import psutil


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _gpu_names():
    """Lấy tên GPU (Windows: WMI; nếu không có thì bỏ qua)."""
    names = []
    try:
        import wmi  # chỉ có trên Windows
        c = wmi.WMI()
        for gpu in c.Win32_VideoController():
            if gpu.Name:
                names.append(gpu.Name.strip())
    except Exception:
        pass
    return names or ["Không xác định"]


def _cpu_name():
    name = platform.processor()
    if name:
        return name
    try:
        import wmi
        c = wmi.WMI()
        for cpu in c.Win32_Processor():
            return cpu.Name.strip()
    except Exception:
        pass
    return platform.machine()


def get_system_info():
    """Trả về dict thông tin máy để hiển thị trên giao diện."""
    vm = psutil.virtual_memory()
    freq = None
    try:
        f = psutil.cpu_freq()
        if f:
            freq = f"{f.max/1000:.2f} GHz" if f.max else f"{f.current/1000:.2f} GHz"
    except Exception:
        freq = None

    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        disks.append({
            "device": part.device,
            "total": _fmt_bytes(usage.total),
            "used": _fmt_bytes(usage.used),
            "free": _fmt_bytes(usage.free),
            "percent": usage.percent,
        })

    return {
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "hostname": socket.gethostname(),
        "arch": platform.machine(),
        "cpu_name": _cpu_name(),
        "cpu_cores": psutil.cpu_count(logical=False) or 0,
        "cpu_threads": psutil.cpu_count(logical=True) or 0,
        "cpu_freq": freq or "—",
        "gpu": _gpu_names(),
        "ram_total": _fmt_bytes(vm.total),
        "python": platform.python_version(),
        "disks": disks,
    }


def get_live_stats():
    """Số liệu thời gian thực (cập nhật định kỳ)."""
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": vm.percent,
        "ram_used": _fmt_bytes(vm.used),
        "ram_total": _fmt_bytes(vm.total),
    }
