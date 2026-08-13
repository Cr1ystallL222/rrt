import json
import psutil
import socket
import subprocess
import time
import urllib.request

def get_network_interfaces() -> list:
    """6. Список сетевых интерфейсов, IP и MAC адресов"""
    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface_name, addr_list in addrs.items():
        stat = stats.get(iface_name)
        is_up = stat.isup if stat else False
        speed = stat.speed if stat else 0

        ipv4 = []
        mac = None
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ipv4.append(addr.address)
            elif hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK:
                mac = addr.address

        if ipv4:
            interfaces.append({
                "name": iface_name,
                "is_up": is_up,
                "speed_mbps": speed,
                "ipv4": ipv4,
                "mac": mac or "N/A"
            })

    return interfaces

def get_active_connections_summary() -> dict:
    """7. Сводка открытых портов и активных сетевых соединений"""
    try:
        conns = psutil.net_connections(kind='inet')
        listening_ports = set()
        established_count = 0

        for c in conns:
            if c.status == psutil.CONN_LISTEN and c.laddr:
                listening_ports.add(c.laddr.port)
            elif c.status == psutil.CONN_ESTABLISHED:
                established_count += 1

        return {
            "total_tracked": len(conns),
            "established_connections": established_count,
            "listening_ports_count": len(listening_ports),
            "sample_listening_ports": sorted(list(listening_ports))[:15]
        }
    except Exception as e:
        return {"error": f"Требуются повышенные права: {str(e)}"}

def test_ping_latency(target: str = "8.8.8.8") -> dict:
    """8. Проверка задержки и стабильности интернет-канала"""
    target = target if target else "8.8.8.8"
    latencies = []
    
    for _ in range(3):
        try:
            start = time.monotonic()
            s = socket.create_connection((target, 53), timeout=2.0)
            s.close()
            latency = round((time.monotonic() - start) * 1000, 1)
            latencies.append(latency)
        except Exception:
            pass

    if not latencies:
        return {"success": False, "target": target, "message": "Узел недоступен (100% потерь)"}

    avg_lat = round(sum(latencies) / len(latencies), 1)
    return {
        "success": True,
        "target": target,
        "avg_ms": avg_lat,
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "packets_sent": 3,
        "packets_recv": len(latencies)
    }

def flush_dns_cache() -> dict:
    """9. Очистка системного кэша DNS"""
    try:
        res = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=5)
        return {
            "success": res.returncode == 0,
            "output": res.stdout.strip() or res.stderr.strip()
        }
    except Exception as e:
        return {"success": False, "output": str(e)}

def get_external_ip() -> dict:
    """10. Определение внешнего публичного IP-адреса"""
    services = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/all.json"
    ]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.68.0'})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode())
                return {"success": True, "data": data}
        except Exception:
            continue

    return {"success": False, "error": "Не удалось связаться с внешними сервисами IP"}
