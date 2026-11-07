import argparse
import json
import httpx

class Client:
    def __init__(self, base_url, tenant, transport=None):
        self.http = httpx.Client(base_url=base_url, headers={'X-Tenant': tenant}, transport=transport)

    def submit(self, key, payload, max_attempts=3):
        response = self.http.post('/jobs', headers={'Idempotency-Key': key},
                                  json={'payload': payload, 'max_attempts': max_attempts})
        response.raise_for_status()
        return response.json()

    def get(self, job_id):
        response = self.http.get('/jobs/' + job_id)
        response.raise_for_status()
        return response.json()

    def cancel(self, job_id):
        response = self.http.post('/jobs/' + job_id + '/cancel')
        response.raise_for_status()
        return response.json()

    def close(self):
        self.http.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8001')
    parser.add_argument('--tenant', required=True)
    parser.add_argument('action', choices=['submit', 'get', 'cancel'])
    parser.add_argument('value', help='idempotency key or job ID')
    parser.add_argument('--payload', default='{}')
    args = parser.parse_args()
    client = Client(args.url, args.tenant)
    try:
        result = client.submit(args.value, json.loads(args.payload)) if args.action == 'submit' else getattr(client, args.action)(args.value)
        print(json.dumps(result, indent=2))
    finally:
        client.close()

if __name__ == '__main__':
    main()
