import asyncio
import os
from threading import Lock, Thread
import time
from typing import Callable

import pynetbox
from fastapi import HTTPException

from misc import logger

max_netbox_fetch_time = 60 * 5
# Bounded cold-start wait for the gate below — fail fast (503) so callers retry
# instead of blocking up to the full fetch window and hitting their own timeout.
init_wait_timeout = 30


class DataLoader(Thread):
    def __init__(self, loop: asyncio.AbstractEventLoop, *args, on_reload: Callable | None = None, on_error: Callable | None = None, **kwargs) -> None:
        super().__init__(*args, daemon=True, **kwargs)
        self.loop = loop
        self.on_reload = on_reload
        self.on_error = on_error
        self.is_initialized = False
        self.needs_reload = True
        self.lock = Lock()
        self.intermediate_data = {
            'interfaces': [],
            'devices': [],
            'ip_addresses': [],
            'tags': [],
            'locations': [],
            'power_ports': []
        }
        self._data = {
            'devices': [],
            'tags': [],
            'locations': []
        }
        self._is_fetching = False
        self._start_fetch_time = time.time()
        self._end_fetch_time = time.time()
        self._stop = False

    def stop(self):
        self._stop = True

    async def __aenter__(self):
        # Bounded wait: on cold start, fail fast with 503 so the caller retries
        # rather than blocking for the whole fetch window past its own timeout.
        deadline = time.monotonic() + init_wait_timeout
        while not self.is_initialized:
            if time.monotonic() > deadline:
                raise HTTPException(status_code=503,
                                    detail='Inventory not loaded yet')
            await asyncio.sleep(1)
        return self

    async def __aexit__(self, *_):
        pass

    @property
    def devices(self):
        with self.lock:
            return self._data['devices']

    @property
    def tags(self):
        with self.lock:
            return self._data['tags']

    @property
    def locations(self):
        with self.lock:
            return self._data['locations']

    def reload(self):
        self.needs_reload = True

    def _watchdog(self):
        while not self._stop:
            if self._is_fetching and (time.time() - self._start_fetch_time) > max_netbox_fetch_time:
                logger.error('DataLoader fetch took too long.')
                # Fire on_error once and stop this loader; on_error spins up a
                # fresh one. Looping here would spawn a new loader every second.
                self._stop = True
                if self.on_error:
                    self.on_error()
                return
            time.sleep(1)

    def run(self):
        apiToken = os.getenv('NETBOX_API_TOKEN')
        nb = pynetbox.api(os.getenv('NETBOX_API_URL'),
                          token=apiToken,
                          threading=True)
        # Verify TLS against a CA bundle when NETBOX_CA_BUNDLE is set; otherwise
        # keep the previous (unverified) behaviour so existing deployments don't
        # break. Set NETBOX_CA_BUNDLE to the internal CA path to harden this.
        nb.http_session.verify = os.getenv('NETBOX_CA_BUNDLE') or False
        try:
            nb.openapi()
        except Exception as e:
            logger.exception(e)
            if self.on_error:
                time.sleep(5)  # debounce respawn while NetBox is unreachable
                self.on_error()
            return

        self._watchdog_thread = Thread(target=self._watchdog, daemon=True)
        self._watchdog_thread.start()

        while not self._stop:
            if self.needs_reload or not self.is_initialized:
                self._is_fetching = True
                self._start_fetch_time = time.time()
                self.intermediate_data['interfaces'] = [
                    dict(interface) for interface in nb.dcim.interfaces.all()]
                self.intermediate_data['ip_addresses'] = [
                    dict(ip_address) for ip_address in nb.ipam.ip_addresses.all()]
                self.intermediate_data['tags'] = [dict(tag)
                                                  for tag in nb.extras.tags.all()]
                self.intermediate_data['locations'] = [
                    dict(location) for location in nb.dcim.locations.all()]
                self.intermediate_data['power_ports'] = list(
                    nb.dcim.power_ports.all())
                self.intermediate_data['devices'] = self._get_devices(
                    [device for device in nb.dcim.devices.all()
                     if device.primary_ip is not None
                     and device['status']['value'] == 'active'])
                self._is_fetching = False
                self.lock.acquire()
                self._data['devices'] = self.intermediate_data['devices'].copy()
                self._data['tags'] = self.intermediate_data['tags'].copy()
                self._data['locations'] = self.intermediate_data['locations'].copy()
                self.lock.release()
                if self.on_reload:
                    asyncio.run_coroutine_threadsafe(
                        self.on_reload(), self.loop)
                self.is_initialized = True
                self.needs_reload = False
            else:
                time.sleep(60)

    def _get_devices(self, rawDevices) -> list:
        devices = []
        for raw in rawDevices:
            device = {
                **dict(raw),
                'interfaces': [dict(interface) for interface in self.intermediate_data['interfaces'] if interface['device']['id'] == raw['id']],
            }
            # Guard the primary_ip lookup: if the IP isn't in the fetched set
            # (filtered/deleted between calls), skip the device instead of
            # IndexError-ing the whole build.
            ip_address = next(
                (ip for ip in self.intermediate_data['ip_addresses']
                 if ip['id'] == device['primary_ip']['id']), None)
            if ip_address is None:
                logger.warning('No primary IP for device %s; skipping',
                               device.get('name'))
                continue
            dev_power_ports = [
                power_port for power_port in self.intermediate_data['power_ports'] if power_port['device']['id'] == raw['id']]
            [[peer.full_details() for peer in p.link_peers]
                for p in dev_power_ports]
            device['power_ports'] = [dict(port) for port in dev_power_ports]
            device['primary_ip'] = dict(ip_address)
            device['tags'] = ip_address['tags']
            if device['status']['value'] == 'active':
                devices.append(device)
        return devices
