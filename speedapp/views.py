# speedapp/views.py
import math
import ipaddress
import os
from datetime import datetime

import requests
import speedtest

from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


# ---------------- Home ----------------
def home(request):
    return render(request, "index.html")


# ---------------- Download test (streamed) ----------------
def testfile(request):
    """
    Streams binary bytes. Query param: kb (kilobytes). Default 8192 KB = 8 MB.
    """
    try:
        kb = int(request.GET.get("kb", 8192))
        kb = max(64, min(kb, 100_000))  # clamp 64KB .. 100MB
    except Exception:
        kb = 8192

    total_bytes = kb * 1024
    chunk_size = 64 * 1024
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


# ---------------- Upload test ----------------
@csrf_exempt
def upload_test(request):
    """
    Accept POST body and return number of bytes received.
    CSRF exempt for easier testing; in production use proper CSRF handling.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        size = len(request.body)
    except Exception:
        size = 0
    return JsonResponse({"status": "ok", "received_bytes": size})


# ---------------- Ping ----------------
def ping(request):
    return HttpResponse("pong")


# ---------------- Helpers for IP detection ----------------
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_private_ip(ip_str):
    try:
        return ipaddress.ip_address(ip_str).is_private
    except Exception:
        return False


# ---------------- Network / ISP detection (HTTPS-safe) ----------------
def network(request):
    """
    Returns ISP name (org), city, country and client IP.
    Uses ipinfo.io via HTTPS. Optionally uses IPINFO_TOKEN env var.
    """
    client_ip = get_client_ip(request) or "unknown"
    private = is_private_ip(client_ip)

    isp = "Unknown"
    city = ""
    country = ""
    lookup_status = ""

    if private:
        isp = "Private Network (LAN)"
        lookup_status = "private"
    else:
        try:
            # Use token if available: set IPINFO_TOKEN env variable to "tokenvalue"
            token = os.environ.get("IPINFO_TOKEN")
            url = "https://ipinfo.io/json"
            headers = {}
            params = {}
            if token:
                params["token"] = token

            r = requests.get(url, headers=headers, params=params, timeout=4)
            data = r.json()
            # ipinfo returns "org" like "AS9829 Reliance Jio Infocomm Limited"
            isp = data.get("org", "Unknown ISP")
            city = data.get("city", "")
            country = data.get("country", "")
            lookup_status = "success"
        except Exception:
            isp = "Lookup Failed"
            lookup_status = "error"

    return JsonResponse({
        "client_ip": client_ip,
        "is_private_ip": private,
        "isp": isp,
        "city": city,
        "country": country,
        "lookup_status": lookup_status,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


# ---------------- Server-side speed test (runs on server) ----------------
def server_speed(request):
    """
    Runs speedtest on the server side (may take 20-60s).
    Be careful: running this frequently will consume server bandwidth and time.
    """
    try:
        s = speedtest.Speedtest()
        s.get_best_server()
        download_b = s.download()
        upload_b = s.upload()
        results = s.results.dict()
        download_mbps = round(download_b / 1_000_000, 2)
        upload_mbps = round(upload_b / 1_000_000, 2)
        ping_ms = round(results.get("ping", 0), 2)
        return JsonResponse({
            "status": "success",
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "ping_ms": ping_ms,
            "server": results.get("server"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)})
