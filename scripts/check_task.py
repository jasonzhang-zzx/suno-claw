#!/usr/bin/env python3
import os, json, requests, urllib3
urllib3.disable_warnings()
API_KEY = os.environ.get("KIEAI_API_KEY", "3429106f44ea713baace08c3b6718b0b")
task_id = "f2217a69ae0aff5d98bd71a1aaa31733"
resp = requests.get(
    f"https://api.kie.ai/api/v1/generate/record-info?taskId={task_id}",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=20,
    verify=False
)
data = resp.json()
print("code:", data.get("code"))
result = data.get("data", {})
print("status:", result.get("status"))
suno_data = (result.get("response") or {}).get("sunoData") or []
for i, item in enumerate(suno_data):
    print(f"歌曲{i+1}: title={item.get('title')}")
    print(f"  audioUrl={item.get('audioUrl')}")
    print(f"  videoUrl={item.get('videoUrl')}")
