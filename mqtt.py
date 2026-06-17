import os
import ssl

from fastapi_mqtt import FastMQTT, MQTTConfig
from gmqtt.mqtt.constants import MQTTv311

CA_CERTIFICATE = '/opt/tls/ca_certificate.pem'
CLIENT_CERTIFICATE = '/opt/tls/client_certificate.pem'
CLIENT_KEY = '/opt/tls/client_key.pem'
ssl_context = ssl.create_default_context(cafile=CA_CERTIFICATE)
ssl_context.load_cert_chain(
    CLIENT_CERTIFICATE, CLIENT_KEY)

mqtt_config = MQTTConfig(
    host=os.environ['MQTT_HOSTNAME'],
    port=8883,
    keepalive=60,
    ssl=ssl_context,
    version=MQTTv311
)

mqtt = FastMQTT(
    config=mqtt_config,
    client_id='api'
)


@mqtt.on_connect()
def mqtt_on_connect(*_):
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    mqtt.client.subscribe('manager/device_event', qos=0)
    mqtt.client.subscribe('manager/tag_event', qos=0)
    mqtt.client.subscribe('manager/location_event', qos=0)
    # Only knx/switch/# is handled by on_message; subscribing to the broader
    # knx/# would rebroadcast unrelated knx/* topics raw (without a target).
    mqtt.client.subscribe('knx/switch/#', qos=0)
