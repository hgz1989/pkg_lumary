"""
@Author     : zarkhan
@CreateDate : 2026/6/17
@Description: 系统资源指标采集模块（纯标准库、多进程支持）
"""
import os
import sys
from multiprocessing import cpu_count
from typing import Any


def get_app_process_pids() -> list[int]:
    """获取当前应用所在进程组的所有 PID。
    
    专门适配 Uvicorn/Gunicorn 的 Master-Worker 架构。
    通过系统进程树，追溯父进程并获取所有同源的工作进程。
    """
    current_pid = os.getpid()
    parent_pid = os.getppid() if hasattr(os, 'getppid') else current_pid

    # 启发式判断：如果父进程是 1 (systemd) 或系统进程，当前可能就是 Master
    master_pid = parent_pid if parent_pid > 1 else current_pid

    # 在 Linux 进一步校验父进程名，如果不是 python/uvicorn/gunicorn，则说明当前进程就是独立主进程
    if sys.platform == 'linux' and master_pid != current_pid:
        try:
            with open(f'/proc/{master_pid}/comm', 'r') as f:
                comm = f.read().strip().lower()
                if 'python' not in comm and 'uvicorn' not in comm and 'gunicorn' not in comm:
                    master_pid = current_pid
        except Exception:
            pass

    pids = [master_pid]

    if sys.platform == 'linux':
        try:
            for d in os.listdir('/proc'):
                if d.isdigit():
                    pid = int(d)
                    if pid == master_pid:
                        continue
                    try:
                        with open(f'/proc/{pid}/stat', 'r') as f:
                            ppid = int(f.read().split()[3])
                            if ppid == master_pid:
                                pids.append(pid)
                    except Exception:
                        pass
        except Exception:
            pass
    elif sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        try:
            TH32CS_SNAPPROCESS = 0x00000002

            class PROCESSENTRY32(ctypes.Structure):  # type: ignore
                _fields_ = [
                    ('dwSize', wintypes.DWORD),
                    ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.POINTER(wintypes.ULONG)),
                    ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', wintypes.LONG),
                    ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_char * 260)
                ]

            hProcessSnap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)  # type: ignore
            if hProcessSnap != -1:
                pe32 = PROCESSENTRY32()
                pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
                if ctypes.windll.kernel32.Process32First(hProcessSnap, ctypes.byref(pe32)):  # type: ignore
                    while True:
                        if pe32.th32ParentProcessID == master_pid and pe32.th32ProcessID != master_pid:
                            pids.append(pe32.th32ProcessID)
                        if not ctypes.windll.kernel32.Process32Next(hProcessSnap, ctypes.byref(pe32)):  # type: ignore
                            break
                ctypes.windll.kernel32.CloseHandle(hProcessSnap)  # type: ignore
        except Exception:
            pass
    else:
        # macOS 等通过 ps 命令兜底
        import subprocess
        try:
            output = subprocess.check_output(['ps', '-o', 'pid,ppid', '-ax'], text=True)
            for line in output.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    pid = int(parts[0])
                    ppid = int(parts[1])
                    if ppid == master_pid and pid != master_pid:
                        pids.append(pid)
        except Exception:
            pass

    if current_pid not in pids:
        pids.append(current_pid)

    return list(set(pids))


def get_system_metrics() -> dict[str, Any]:
    """获取系统运行指标，聚合多进程资源
    
    Returns:
        包含内存、CPU、磁盘和进程数量的字典
    """
    pids = get_app_process_pids()
    workers_count = len(pids)

    memory_mb = 0.0

    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):  # type: ignore
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
                ('PrivateUsage', ctypes.c_size_t),
            ]

        for pid in pids:
            try:
                # 0x0410 = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                process_handle = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid)  # type: ignore
                if process_handle:
                    counters = PROCESS_MEMORY_COUNTERS_EX()
                    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(process_handle, ctypes.byref(counters),
                                                                ctypes.sizeof(counters)):  # type: ignore
                        memory_mb += counters.WorkingSetSize / 1024 / 1024
                    ctypes.windll.kernel32.CloseHandle(process_handle)  # type: ignore
            except Exception:
                pass
    elif sys.platform == 'linux':
        for pid in pids:
            try:
                with open(f'/proc/{pid}/status', 'r') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            kb = int(line.split()[1])
                            memory_mb += kb / 1024
                            break
            except Exception:
                pass
    else:
        import subprocess
        try:
            output = subprocess.check_output(['ps', '-p', ','.join(map(str, pids)), '-o', 'rss='], text=True)
            for line in output.splitlines()[1:]:
                try:
                    kb = int(line.strip())
                    memory_mb += kb / 1024
                except ValueError:
                    pass
        except Exception:
            pass

    if memory_mb == 0.0:
        memory_mb = -1.0

    # CPU 模拟: 纯标准库无法在一次请求中无阻塞地精确计算各进程实时 CPU 和。
    # 这里采用系统 1 分钟平均负载来估算整体繁忙度
    cpu_percent = 0.0
    if hasattr(os, 'getloadavg'):
        try:
            load1, _, _ = os.getloadavg()
            cpu_percent = round((load1 / cpu_count()) * 100, 2)
        except Exception:
            pass

    # 磁盘使用率
    disk_usage_percent = 0.0
    try:
        if sys.platform == 'win32':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            total_free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(  # type: ignore
                ctypes.c_wchar_p("C:\\"),
                ctypes.byref(free_bytes),
                ctypes.byref(total_bytes),
                ctypes.byref(total_free_bytes)
            )
            used_bytes = total_bytes.value - free_bytes.value
            if total_bytes.value > 0:
                disk_usage_percent = round((used_bytes / total_bytes.value) * 100, 2)
        else:
            st = os.statvfs('/')
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            if total > 0:
                disk_usage_percent = round((used / total) * 100, 2)
    except Exception:
        pass

    return {
        'memory_mb': round(memory_mb, 2),
        'cpu_percent': cpu_percent,
        'disk_usage_percent': disk_usage_percent,
        'workers_count': workers_count
    }
