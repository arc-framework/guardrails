import asyncio
import json
from fastapi.testclient import TestClient
from arc_guard_service.transport.http import create_app
from arc_guard_service.settings import ServiceSettings

async def main():
    # Use ServiceSettings(backend='echo') with defaults
    settings = ServiceSettings(backend='echo')
    app = create_app(settings=settings)
    
    email = "alice.test00000@fixture.invalid"
    phone = "555-867-0000"
    
    with TestClient(app) as client:
        # Send one chat completion
        payload = {
            "messages": [{"role": "user", "content": f"My email is {email} and phone is {phone}"}],
            "model": "gpt-4o",
            "user": "sec-test-00000" # Adding user to ensure lifecycle ID is predictable or traceable
        }
        # In many systems the user ID or a trace header might map to the lifecycle ID. 
        # The prompt says fetch /lifecycle/sec-test-00000, suggesting sec-test-00000 is the ID.
        client.post("/v1/chat/completions", json=payload, headers={"X-Request-ID": "sec-test-00000"})
        
        response = client.get("/lifecycle/sec-test-00000")
        if response.status_code != 200:
            # Try searching for other likely IDs if 200 is not returned
            pass
            
        data = response.json()
        
        leaks = []
        events = data if isinstance(data, list) else data.get("events", [])
        
        for event in events:
            event_str = json.dumps(event)
            if email in event_str or phone in event_str:
                leaked_fields = []
                def check_leak(d, prefix=""):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            check_leak(v, f"{prefix}.{k}" if prefix else k)
                    elif isinstance(d, list):
                        for i, v in enumerate(d):
                            check_leak(v, f"{prefix}[{i}]")
                    else:
                        if email in str(d) or phone in str(d):
                            leaked_fields.append(prefix)
                
                check_leak(event)
                leaks.append({
                    "event_type": event.get("event_type", "unknown"),
                    "fields": leaked_fields
                })
        
        for leak in leaks:
            print(json.dumps(leak))

if __name__ == "__main__":
    asyncio.run(main())
