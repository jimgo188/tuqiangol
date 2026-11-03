"""Constants for the 途强在线 integration."""

DOMAIN = "tuqiangol"
NAME = "途强在线"
DEFAULT_HOST = "https://www.tuqiangol.com"
DEFAULT_SCAN_INTERVAL = 60

CONF_DEVICE_IMEIS = "device_imeis"
CONF_COORDINATE_SYSTEM = "coordinate_system"
CONF_HIGH_PRECISION_ADDRESS = "high_precision_address"

COORDINATE_SYSTEMS = ("wgs84", "gcj02", "bd09")

ATTR_ADDRESS = "address"
ATTR_GPS_TIME = "gps_time"
ATTR_HEARTBEAT_TIME = "heartbeat_time"
ATTR_POSITION_TYPE = "position_type"
ATTR_SPEED = "speed"
ATTR_DIRECTION = "direction"
ATTR_ACC = "acc"
ATTR_POWER_STATUS = "power_status"
ATTR_EXTERNAL_VOLTAGE = "external_voltage"
ATTR_TOTAL_MILEAGE = "total_mileage"
ATTR_GPS_SIGNAL = "gps_signal"
ATTR_STATUS = "status"
ATTR_RAW = "raw"
