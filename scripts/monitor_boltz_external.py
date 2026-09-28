"""Collect the frozen pilot promptly, using the proxy-compatible research UA for Phase 18.

Runpod's proxy rejects the default Python urllib user agent with HTTP 403/1010.
This transport-only compatibility wrapper leaves the frozen scientific inputs
and deployed worker unchanged. The independent deadline watchdog remains active.
"""
import argparse
import json
import time
import urllib.request

import runpod_boltz_external as pilot

original_request = pilot.request


def research_request(*args, **kwargs):
    req = original_request(*args, **kwargs)
    req.add_header('User-Agent', 'cryo-research/0.1')
    return req


pilot.request = research_request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    state = pilot.load(pilot.LOCAL/f'attempt{args.attempt}'/'state.json')
    previous = None
    startup_deadline = state['created_epoch'] + 900
    while time.time() < state['deadline_epoch']-45:
        if previous is None and time.time() > startup_deadline:
            receipt = pilot.finish(state, {'failure': 'No reachable worker within 15 minute startup limit'})
            print(json.dumps({'deleted': receipt['deleted'], 'reason': 'startup deadline'}), flush=True)
            return
        if pilot.receipt_path(state).exists() and pilot.load(pilot.receipt_path(state)).get('deleted'):
            return
        try:
            with urllib.request.urlopen(pilot.request(state, 'status'), timeout=15) as response:
                status = json.load(response)
            pilot.write_json(pilot.LOCAL/f'attempt{args.attempt}'/'last-worker-status.json', status)
            if status['state'] != previous:
                print(json.dumps({'worker_state': status['state'], 'time_epoch': time.time()}), flush=True)
                previous = status['state']
            if status.get('results_ready'):
                print(json.dumps(pilot.collect(state)), flush=True)
                return
            if status['state'] == 'awaiting_inputs':
                pilot.upload(state)
        except Exception as exc:
            print(json.dumps({'poll_error': type(exc).__name__, 'time_epoch': time.time()}), flush=True)
        time.sleep(20)
    receipt = pilot.finish(state, {'failure': 'monitor collection deadline'})
    print(json.dumps({'deleted': receipt['deleted'], 'reason': 'deadline'}), flush=True)


if __name__ == '__main__':
    main()
