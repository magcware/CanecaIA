import paho.mqtt.publish as publish
from app.config import MQTT_HOST, MQTT_PORT, MQTT_TOPIC


def publish_result(result: str):

    publish.single(
        MQTT_TOPIC,
        result,
        hostname=MQTT_HOST,
        port=MQTT_PORT,
        retain=False
    )