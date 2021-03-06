"""Support for interface with an Samsung TV."""
import asyncio
from datetime import timedelta
import logging
import socket
import json
import voluptuous as vol
import os
import websocket
import wakeonlan
import time
import requests
import subprocess

from .PySmartCrypto.pysmartcrypto import PySmartCrypto

from homeassistant import util
from homeassistant.components.media_player import MediaPlayerDevice, PLATFORM_SCHEMA
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_SET,
    MEDIA_TYPE_URL,
    MEDIA_TYPE_VIDEO,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_APP
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MEDIA_TYPE_KEY = "send_key"
DEFAULT_NAME = "Samsung TV Remote"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 2
KEY_PRESS_TIMEOUT = 1.2
KNOWN_DEVICES_KEY = "samsungtv_known_devices"
SOURCES = {"TV": "KEY_TV", "HDMI": "KEY_HDMI"}
CONF_SOURCELIST = "sourcelist"
CONF_APPLIST = "applist"
CONF_TOKEN = "token"
CONF_SESSIONID = "sessionid"
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=2)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SUPPORT_SAMSUNGTV = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_NEXT_TRACK
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_MAC): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_SOURCELIST): cv.string,
        vol.Optional(CONF_APPLIST): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_SESSIONID): cv.string,
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Samsung TV platform."""
    known_devices = hass.data.get(KNOWN_DEVICES_KEY)
    if known_devices is None:
        known_devices = set()
        hass.data[KNOWN_DEVICES_KEY] = known_devices

    uuid = None
    
    if config.get(CONF_SOURCELIST) is not None:
        sourcelist = json.loads(config.get(CONF_SOURCELIST))
    else:
        sourcelist = SOURCES

    if config.get(CONF_APPLIST) is not None:
        applist = config.get(CONF_APPLIST).split(", ")
    else:
        applist = []

    # Is this a manual configuration?
    if config.get(CONF_HOST) is not None:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        name = config.get(CONF_NAME)
        mac = config.get(CONF_MAC)
        timeout = config.get(CONF_TIMEOUT)
        token = config.get(CONF_TOKEN)
        sessionid = config.get(CONF_SESSIONID)
    elif discovery_info is not None:
        tv_name = discovery_info.get("name")
        model = discovery_info.get("model_name")
        host = discovery_info.get("host")
        name = f"{tv_name} ({model})"
        port = DEFAULT_PORT
        timeout = DEFAULT_TIMEOUT
        token = "0"
        sessionid = "0"
        mac = None
        udn = discovery_info.get("udn")
        if udn and udn.startswith("uuid:"):
            uuid = udn[len("uuid:") :]
    else:
        _LOGGER.warning("Cannot determine device")
        return

    # Only add a device once, so discovered devices do not override manual
    # config.
    ip_addr = socket.gethostbyname(host)
    if ip_addr not in known_devices:
        #known_devices.add(ip_addr)
        add_entities([SamsungTVDevice(host, port, name, timeout, mac, uuid, sourcelist, token, sessionid)])
        _LOGGER.info("Samsung TV %s:%d added as '%s'", host, port, name)
    else:
        _LOGGER.info("Ignoring duplicate Samsung TV %s:%d", host, port)

class SamsungTVDevice(MediaPlayerDevice):
    """Representation of a Samsung TV."""

    def __init__(self, host, port, name, timeout, mac, uuid, sourcelist, token, sessionid):
        """Initialize the Samsung device."""
        # Save a reference to the imported classes
        self._host = host
        self._port = port
        self._token = token
        self._sessionid = sessionid
        self._remote_class = PySmartCrypto
        self._name = name
        self._mac = mac
        self._uuid = uuid
        self._wol = wakeonlan
        # Assume that the TV is not muted
        self._muted = False
        # Assume that the TV is in Play mode
        self._playing = True
        self._state = None
        self._remote = None
        # Mark the end of a shutdown command (need to wait 15 seconds before
        # sending the next command to avoid turning the TV back ON).
        self._end_of_power_off = None
        # Generate a configuration for the Samsung library
        self._config = {
            "name": "HomeAssistant",
            "description": name,
            "id": "ha.component.samsung",
            "port": port,
            "host": host,
            "timeout": timeout,
        }
        self._sourcelist = sourcelist

    def update(self):
        """Update state of device."""
        self.send_key("KEY")

    def pingTV(self):
        """ping TV"""
        cmd = ['ping', '-c1', '-W2', self._host ]
        response = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdout, stderr = response.communicate()
        if response.returncode == 0:   
            return True
        else:
            return False
        
    def get_remote(self):
        """Create or return a remote control instance."""
        if self._remote is None:
            # We need to create a new instance to reconnect.
            self._remote = self._remote_class(self._host, self._port, self._token, self._sessionid)

        return self._remote

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        if self._power_off_in_progress() and key not in ("KEY_POWER", "KEY_POWEROFF"):
            _LOGGER.info("TV is powering off, not sending command: %s", key)
            return
        
        # first try pinging the TV
        if not self.pingTV():
            self._state = STATE_OFF
            #self.get_remote().close()
            self._remote = None
            return
        
        try:
            # recreate connection if connection was dead
            retry_count = 1
            for _ in range(retry_count + 1):
                try:
                    self.get_remote().control(key)
                    break
                except:
                    # BrokenPipe can occur when the commands is sent to fast
                    # WebSocketException can occur when timed out
                    self._remote = None
            self._state = STATE_ON
        except:
            # We got a response so it's on.
            self._state = STATE_ON
            self._remote = None
            LOGGER.debug("Failed sending command %s", key, exc_info=True)
            return
        if self._power_off_in_progress():
            self._state = STATE_OFF

    def _power_off_in_progress(self):
        return (
            self._end_of_power_off is not None
            and self._end_of_power_off > dt_util.utcnow()
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device."""
        return self._uuid

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._sourcelist)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mac:
            return SUPPORT_SAMSUNGTV | SUPPORT_TURN_ON
        return SUPPORT_SAMSUNGTV

    def volume_up(self):
        """Volume up the media player."""
        self.send_key("KEY_VOLUP")

    def volume_down(self):
        """Volume down media player."""
        self.send_key("KEY_VOLDOWN")

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_key("KEY_MUTE")

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self.send_key("KEY_PLAY")

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self.send_key("KEY_PAUSE")

    def media_next_track(self):
        """Send next track command."""
        self.send_key("KEY_FF")

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_key("KEY_REWIND")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""

        if media_type == MEDIA_TYPE_CHANNEL:
        # media_id should only be a channel number
            try:
                cv.positive_int(media_id)
            except vol.Invalid:
                _LOGGER.error("Media ID must be positive integer")
                return
    
            for digit in media_id:
                await self.hass.async_add_job(self.send_key, "KEY_" + digit)
                await asyncio.sleep(KEY_PRESS_TIMEOUT, self.hass.loop)
            await self.hass.async_add_job(self.send_key, "KEY_ENTER")
        elif media_type == MEDIA_TYPE_KEY:
            self.send_key(media_id)
        else:
            _LOGGER.error("Unsupported media type")
            return

    def turn_off(self):
        """Turn off media player."""
        self._end_of_power_off = dt_util.utcnow() + timedelta(seconds=15)

        self.send_key("KEY_POWEROFF")
        # Force closing of remote session to provide instant UI feedback
        try:
            self.get_remote().close()
            self._remote = None
        except OSError:
            _LOGGER.debug("Could not establish connection.")

    def turn_on(self):
        """Turn the media player on."""
        if self._mac:
            wakeonlan.send_magic_packet(self._mac)
        else:
            self.send_key("KEY_POWERON")

    async def async_select_source(self, source):
        """Select input source."""
        await self.hass.async_add_job(self.send_key, self._sourcelist[source])
