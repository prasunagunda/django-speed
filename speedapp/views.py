import math
import ipaddress
import subprocess
from datetime import datetime

from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import requests


# ---------- Home page ----------
def home(request):
    return render(request, "index.html")


# ---------- Download test ----------
def testfile(request):
    try:
        kb = int(request.GET.get("kb", 5120))
        kb = max(64, min(kb, 50000))
    except:
        kb = 5120

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
    resp["Cache-Control"] = "no-store"
    return resp


# ---------- Upload test ----------
@csrf_exempt
def upload_test(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    size = len(request.body) if request.body else 0
    return JsonResponse({"status": "ok", "received_bytes": size})


# ---------- Ping ----------
def ping(request):
    return HttpResponse("pong")


# ---------- Client IP ----------
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_private_ip(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except:
        return False


# ---------- Network / ISP detection ----------
def network(request):
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
            # HTTPS-safe ISP lookup
            r = requests.get("https://ipinfo.io/json", timeout=4)
            data = r.json()
            isp = data.get("org", "Unknown ISP")
            city = data.get("city", "")
            country = data.get("country", "")
            lookup_status = "success"
        except:
            isp = "Lookup Failed"
            lookup_status = "error"

    return JsonResponse({
        "client_ip": client_ip,
        "isp": isp,
        "city": city,
        "country": country,
        "lookup_status": lookup_status,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
