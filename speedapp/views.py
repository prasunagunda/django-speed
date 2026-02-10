# speedapp/views.py
import math
import ipaddress
import subprocess
from datetime import datetime

from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

# Optional: if you want IP -> ISP lookup
import requests

# ---------- Home (render template) ----------
def home(request):
    return render(request, "index.html")


# ---------- Streaming test file (download) ----------
def testfile(request):
    """
    Streams binary bytes. Query param: kb (kilobytes). Default 5120 KB = 5 MB.
    Streaming response prevents buffering server-side so browser receives real stream.
    """
    try:
        kb = int(request.GET.get("kb", 5120))
        kb = max(64, min(kb, 50_000))  # clamp: 64 KB .. 50 MB
    except Exception:
        kb = 5120

    total_bytes = kb * 1024
    chunk_size = 64 * 1024  # 64 KB
    chunks = math.ceil(total_bytes / chunk_size)

    def stream():
        sent = 0
        chunk = b"\0" * chunk_size
        for _ in range(chunks):
            remaining = total_bytes - sent
            if remaining <= 0:
                break
            if remaining < chunk_size:
                yield b"\0" * remaining
                sent += remaining
            else:
                yield chunk
                sent += chunk_size

    resp = StreamingHttpResponse(stream(), content_type="application/octet-stream")
    resp["Content-Length"] = str(total_bytes)
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


# ---------- Upload test endpoint ----------
@csrf_exempt
def upload_test(request):
    """
    Accept POST body and return number of bytes received.
    Keep CSRF exempt for easy testing; for production use CSRF token.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        size = len(request.body)
    except Exception:
        size = 0
    return JsonResponse({"status": "ok", "received_bytes": size})


# ---------- Ping endpoint ----------
def ping(request):
    return HttpResponse("pong")


# ---------- Utility: attempt to get server WiFi SSID (works only on Windows) ----------
def get_wifi_name_windows():
    try:
        output = subprocess.check_output(
            "netsh wlan show interfaces",
            shell=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        for line in output.splitlines():
            line = line.strip()
            if line.lower().startswith("ssid") and "bssid" not in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
                    if ssid:
                        return ssid
    except Exception:
        pass
    return "Server-Network-Unknown"


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        ip = xff.split(",")[0].strip()
        if ip:
            return ip
    return request.META.get("REMOTE_ADDR") or ""


def is_private_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return ip_obj.is_private or ip_obj.is_loopback
    except Exception:
        return False


def network(request):
    """
    Optional endpoint: returns client IP and ISP info.
    If client IP is private, skip lookup.
    """
    client_ip = get_client_ip(request) or "unknown"
    private = is_private_ip(client_ip)

    isp = "Unknown"
    org = ""
    city = ""
    country = ""
    lookup_status = ""

    if private:
        lookup_status = "private_ip_no_lookup"
        isp = "Private Network (LAN)"
    else:
        try:
            # Using https for ip-api
            r = requests.get(
                f"https://ip-api.com/json/{client_ip}?fields=status,isp,org,city,country,message",
                timeout=4,
            )
            data = r.json()
            if data.get("status") == "success":
                isp = data.get("isp") or "Unknown"
                org = data.get("org") or ""
                city = data.get("city") or ""
                country = data.get("country") or ""
                lookup_status = "success"
            else:
                lookup_status = "fail"
                isp = data.get("message", "Lookup failed")
        except Exception:
            lookup_status = "error"
            isp = "Lookup Failed"

    server_ssid = get_wifi_name_windows()

    return JsonResponse(
        {
            "client_ip": client_ip,
            "is_private_ip": private,
            "lookup_status": lookup_status,
            "isp": isp,
            "org": org,
            "city": city,
            "country": country,
            "server_ssid": server_ssid,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
