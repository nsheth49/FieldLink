"""Explicit opt-in harmless live tool call. Never messages a phone."""
import argparse
import json
from check_integrations import nvidia_smoke

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    if not args.live: raise SystemExit('Requires --live and NVIDIA_API_KEY in ignored .env')
    result=nvidia_smoke()
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
