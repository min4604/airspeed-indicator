import threading
import queue
import sys
import time
import os
from typing import Optional, Deque, Dict, Any
from collections import deque

try:
	import serial
	import serial.tools.list_ports as list_ports
except ImportError:
	serial = None  # Will be checked at runtime
	list_ports = None

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# ==== Optional Flask Web Server (for HTML dashboard) ====
_flask_available = False
try:
	from flask import Flask, jsonify, render_template, Response, request
	_flask_available = True
except Exception:
	_flask_available = False

# ==== Shared Data Store for Web Frontend ====
DATA_LOCK = threading.Lock()
LATEST: Dict[str, Any] = {}
SERIES: Deque[Dict[str, Any]] = deque(maxlen=600)  # ~ last 10 minutes at 1s sampling
UPDATE_EVENT = threading.Event()  # Signal when new data is available
QNH_PRESSURE = 1013.25  # Default QNH in hPa

# ==== PDUS Differential Pressure Filter ====
PDUS_FILTER_SIZE = 10  # Moving average window size
PDUS_PRESSURE_BUFFER: Deque[float] = deque(maxlen=PDUS_FILTER_SIZE)


class SerialReader:
	"""
	Background serial reader that pushes received bytes into a queue.
	Supports auto-reconnection on disconnection.
	Supports packet framing using idle time detection.

	Contract:
	- input: open parameters (port, baudrate, auto_reconnect, packet_timeout)
	- output: places raw bytes objects into the provided Queue
	- stop: safe shutdown on .stop(); closes port
	- errors: raises RuntimeError if port can't open
	"""

	def __init__(self, port: str, baudrate: int, out_queue: queue.Queue, auto_reconnect: bool = True, max_retries: int = 5, retry_interval: float = 2.0, packet_timeout: float = 0.05):
		self.port = port
		self.baudrate = baudrate
		self._q = out_queue
		self.auto_reconnect = auto_reconnect
		self.max_retries = max_retries
		self.retry_interval = retry_interval
		self.packet_timeout = packet_timeout  # Idle time to consider packet complete (50ms default)
		# Use a broad type here to avoid type issues when pyserial isn't installed during analysis
		self._ser: Optional[object] = None
		self._t: Optional[threading.Thread] = None
		self._running = threading.Event()
		self._reconnect_count = 0

	def start(self):
		if serial is None:
			raise RuntimeError("pyserial 未安裝，請先安裝 pyserial 套件")

		if self._t and self._t.is_alive():
			return
		try:
			self._ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
		except Exception as e:
			raise RuntimeError(f"無法開啟序列埠 {self.port}: {e}") from e

		self._running.set()
		self._t = threading.Thread(target=self._loop, daemon=True)
		self._t.start()

	def _loop(self):
		assert self._ser is not None
		ser = self._ser
		packet_buffer = bytearray()  # Buffer to accumulate packet data
		last_received_time = None
		
		while self._running.is_set():
			try:
				n = ser.in_waiting
				current_time = time.time()
				
				if n:
					# Data available - read it
					data = ser.read(n)
					if data:
						packet_buffer.extend(data)
						last_received_time = current_time
						self._reconnect_count = 0  # Reset on successful read
						
						# Try to extract complete packets based on protocol
						while True:
							extracted_packet = self._extract_packet(packet_buffer)
							if extracted_packet:
								self._q.put(extracted_packet)
							else:
								break
				else:
					# No data available
					# Check if we have buffered data and enough idle time has passed
					if packet_buffer and last_received_time:
						idle_time = current_time - last_received_time
						if idle_time >= self.packet_timeout:
							# Timeout - send whatever we have (might be incomplete/corrupted)
							if packet_buffer:
								self._q.put({"incomplete": bytes(packet_buffer)})
								packet_buffer.clear()
							last_received_time = None
					
					# Small sleep to prevent busy-waiting
					time.sleep(0.001)
					
			except Exception as e:
				# Send any buffered data before handling error
				if packet_buffer:
					self._q.put({"incomplete": bytes(packet_buffer)})
					packet_buffer.clear()
				
				# Connection lost
				self._q.put_nowait({"error": str(e)})
				
				if not self.auto_reconnect or not self._running.is_set():
					break
				
				# Attempt auto-reconnection
				if self._reconnect_count < self.max_retries:
					self._reconnect_count += 1
					self._q.put_nowait({"reconnect": self._reconnect_count, "max": self.max_retries})
					
					# Close the failed connection
					try:
						if self._ser:
							self._ser.close()
					except Exception:
						pass
					
					# Wait before retry
					time.sleep(self.retry_interval)
					
					# Try to reconnect
					try:
						self._ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
						ser = self._ser
						self._q.put_nowait({"reconnect_success": True})
						last_received_time = None
						packet_buffer.clear()
						continue
					except Exception as reconnect_err:
						self._q.put_nowait({"reconnect_error": str(reconnect_err)})
						continue
				else:
					# Max retries reached
					self._q.put_nowait({"reconnect_failed": True})
					break

	def _extract_packet(self, buffer: bytearray) -> Optional[bytes]:
		"""
		Extract a complete packet from buffer based on protocol:
		- Byte 0-1: Header (0x02 0x00)
		- Byte 2: Length of following data
		- Byte 3+: Data (length bytes)
		
		Returns the complete packet and removes it from buffer, or None if incomplete.
		"""
		# Need at least 3 bytes to check header and length
		if len(buffer) < 3:
			return None
		
		# Check for valid header (0x02 0x00)
		if buffer[0] != 0x02 or buffer[1] != 0x00:
			# Invalid header - try to find next valid header
			for i in range(1, len(buffer) - 1):
				if buffer[i] == 0x02 and buffer[i + 1] == 0x00:
					# Found potential header, discard everything before it
					discarded = bytes(buffer[:i])
					del buffer[:i]
					self._q.put({"discarded": discarded})
					return None
			# No valid header found, keep last byte in case it's start of 0x02 0x00
			if len(buffer) > 1:
				discarded = bytes(buffer[:-1])
				del buffer[:-1]
				self._q.put({"discarded": discarded})
			return None
		
		# Valid header found, get length
		data_length = buffer[2]
		total_length = 3 + data_length  # header(2) + length(1) + data(length)
		
		# Check if we have complete packet
		if len(buffer) < total_length:
			return None  # Wait for more data
		
		# Extract complete packet
		packet = bytes(buffer[:total_length])
		del buffer[:total_length]
		
		return packet

	def stop(self):
		self._running.clear()
		if self._t and self._t.is_alive():
			self._t.join(timeout=1.0)
		if self._ser:
			try:
				self._ser.close()
			except Exception:
				pass
		self._t = None
		self._ser = None


def calculate_pressure_altitude(pressure_kpa: float, temperature_c: float = 15.0, qnh_hpa: float = None) -> dict:
	"""
	Calculate pressure altitude from atmospheric pressure.
	Uses the International Standard Atmosphere (ISA) model.
	
	Args:
		pressure_kpa: Atmospheric pressure in kPa
		temperature_c: Temperature in Celsius (used for density altitude calculation)
		qnh_hpa: QNH pressure setting in hPa (if None, uses standard 1013.25)
	
	Returns:
		Dictionary containing:
		- pressure_altitude_m: Pressure altitude in meters (ISA standard)
		- pressure_altitude_ft: Pressure altitude in feet (ISA standard)
		- qnh_altitude_m: QNH corrected altitude in meters
		- qnh_altitude_ft: QNH corrected altitude in feet
		- density_altitude_m: Density altitude in meters (optional)
		- density_altitude_ft: Density altitude in feet (optional)
	"""
	import math
	
	result = {}
	
	try:
		# Convert to Pa
		pressure_pa = pressure_kpa * 1000.0
		
		# ISA standard values
		P0_standard = 101325.0  # Sea level standard pressure in Pa (1013.25 hPa)
		T0 = 288.15    # Sea level standard temperature in K (15°C)
		L = -0.0065    # Temperature lapse rate in K/m
		g = 9.80665    # Gravitational acceleration in m/s²
		R = 287.05     # Specific gas constant for dry air in J/(kg·K)
		
		exponent = -(R * L) / g
		
		# Calculate standard pressure altitude (based on ISA 1013.25 hPa)
		pressure_ratio_standard = pressure_pa / P0_standard
		if pressure_ratio_standard > 0:
			pressure_altitude_m = (T0 / L) * (math.pow(pressure_ratio_standard, exponent) - 1)
			result['pressure_altitude_m'] = pressure_altitude_m
			result['pressure_altitude_ft'] = pressure_altitude_m * 3.28084
		else:
			result['pressure_altitude_m'] = 0.0
			result['pressure_altitude_ft'] = 0.0
		
		# Calculate QNH altitude if QNH is provided
		if qnh_hpa is not None:
			P0_qnh = qnh_hpa * 100.0  # Convert hPa to Pa
			pressure_ratio_qnh = pressure_pa / P0_qnh
			
			if pressure_ratio_qnh > 0:
				qnh_altitude_m = (T0 / L) * (math.pow(pressure_ratio_qnh, exponent) - 1)
				result['qnh_altitude_m'] = qnh_altitude_m
				result['qnh_altitude_ft'] = qnh_altitude_m * 3.28084
			else:
				result['qnh_altitude_m'] = 0.0
				result['qnh_altitude_ft'] = 0.0
			
			result['qnh_hpa'] = qnh_hpa
		
		# Calculate density altitude (pressure altitude corrected for non-standard temperature)
		if 'pressure_altitude_m' in result:
			temperature_k = temperature_c + 273.15
			# ISA temperature at pressure altitude
			T_isa = T0 + L * result['pressure_altitude_m']
			
			# Density altitude formula: DA = PA + 120 * (T - T_ISA)
			# More accurate formula using density ratio
			density_ratio = (T_isa / temperature_k)
			density_altitude_m = result['pressure_altitude_m'] + (T_isa / L) * (1 - density_ratio)
			
			result['density_altitude_m'] = density_altitude_m
			result['density_altitude_ft'] = density_altitude_m * 3.28084
		
		result['pressure_kpa'] = pressure_kpa
		result['temperature_c'] = temperature_c
		
	except Exception as e:
		result['error'] = str(e)
		result['pressure_altitude_m'] = 0.0
		result['pressure_altitude_ft'] = 0.0
	
	return result

def decoder(data: bytes) -> dict:
	"""
	Decode sensor data from the packet.
	Returns a dictionary with all sensor readings.
	"""
	result = {}
	
	try:
		# HIDS_temperature decoder 
		if len(data) >= 5:
			raw_value = (data[3] << 8) + data[4]
			result['temperature_HIDS'] = -45.0 + 175.0 * raw_value / 65535.0

		# HIDS_humidity decoder
		if len(data) >= 9:
			raw_value = (data[6] << 8) + data[7]
			result['humidity_HIDS'] = 100.0 * raw_value / 65535.0
		
		# PADS_pressure decoder Kpa
		if len(data) >= 12:
			raw_value = (data[11] << 16) + (data[10] << 8) + data[9]
			result['pressure_PADS'] =raw_value / 40960.0

		# PADS_temperature decoder
		if len(data) >= 14:
			raw_value = (data[13] << 8) + data[12]
			result['temperature_PADS'] = raw_value / 100.0
		
		# PDUS_diffential_pressure decoder pa
		# Precision: 7.63e-5 kPa/digit = 0.0763 Pa/digit
		# Range: -1kPa ~ 1kPa (-1000Pa ~ 1000Pa)
		# Zero offset at raw_value ≈ 32768 for 16-bit ADC 3277
		if len(data) >= 16:
			raw_value = (data[14] << 8) + data[15]
			# Convert to Pa: (raw - zero_offset) * sensitivity
			pressure_raw = (raw_value - 16384) * 0.07629511 - 6.1 #壓差校正
			
			# Apply moving average filter to reduce noise
			PDUS_PRESSURE_BUFFER.append(pressure_raw)
			if len(PDUS_PRESSURE_BUFFER) > 0:
				result['pressure_PDUS'] = sum(PDUS_PRESSURE_BUFFER) / len(PDUS_PRESSURE_BUFFER)
			else:
				result['pressure_PDUS'] = pressure_raw

		# PDUS_temperature decoder
		if len(data) >= 18:
			raw_value = (data[16] << 8) + data[17]
			result['temperature_PDUS'] = (raw_value - 8192) * 4.27e-3
		
		# Calculate altitude from pressure if we have pressure data
		if 'pressure_PADS' in result:
			# Use PADS temperature if available, otherwise use HIDS or PDUS temperature
			temp_for_altitude = result.get('temperature_PADS', result.get('temperature_HIDS', result.get('temperature_PDUS', 15.0)))
			result['altitude'] = calculate_pressure_altitude(
				result['pressure_PADS'],  # In kPa
				temp_for_altitude,
				QNH_PRESSURE  # Use global QNH setting
			)
		
		# Calculate airspeed if we have all necessary data
		if 'pressure_PDUS' in result and 'pressure_PADS' in result and 'temperature_PDUS' in result and 'humidity_HIDS' in result:
			result['airspeed'] = calculate_airspeed(
				result['pressure_PDUS'],  # Already in Pa
				result['pressure_PADS'] * 1000.0,  # Convert kPa to Pa
				result['temperature_PDUS'],
				result['humidity_HIDS']
			)
	
	except Exception as e:
		result['error'] = str(e)
	
	return result


def calculate_airspeed(differential_pressure: float, static_pressure_pa: float, temperature_c: float, humidity_percent: float = 0.0) -> dict:
	"""
	Calculate airspeed using three different methods:
	- ISA (Indicated Airspeed): Uses ISA standard density at sea level (1.225 kg/m³)
	- CAS (Calibrated Airspeed): Uses standard density corrected for altitude via pressure
	- TAS (True Airspeed): Uses actual air density from temperature, pressure, and humidity
	
	Args:
		differential_pressure: Differential pressure from PDUS sensor in Pa
		static_pressure_pa: Static atmospheric pressure in Pa
		temperature_c: Temperature in Celsius
		humidity_percent: Relative humidity in percent (0-100)
	
	Returns:
		Dictionary with all three airspeed types in different units
	"""
	import math
	
	result = {}
	
	try:
		# PDUS sensor differential pressure already in Pa
		delta_p_pa = differential_pressure
		result['differential_pressure_pa'] = delta_p_pa
		
		if delta_p_pa <= 0:
			# No forward airspeed
			result['IAS_ms'] = 0.0
			result['IAS_kmh'] = 0.0
			result['IAS_knots'] = 0.0
			result['CAS_ms'] = 0.0
			result['CAS_kmh'] = 0.0
			result['CAS_knots'] = 0.0
			result['TAS_ms'] = 0.0
			result['TAS_kmh'] = 0.0
			result['TAS_knots'] = 0.0
			return result
		
		# ISA Standard sea level density
		rho_isa = 1.225  # kg/m³
		
		# Calculate ISA (Indicated Airspeed) - uses standard sea level density
		IAS_ms = math.sqrt(2.0 * delta_p_pa / rho_isa)
		result['IAS_ms'] = IAS_ms
		result['IAS_kmh'] = IAS_ms * 3.6
		result['IAS_knots'] = IAS_ms * 1.94384
		
		# Calculate CAS (Calibrated Airspeed) - density corrected for altitude via pressure
		# Use ISA standard temperature lapse to estimate density from pressure
		static_pressure_pa = static_pressure_pa
		# ISA standard: P0 = 101325 Pa, T0 = 288.15 K, L = -0.0065 K/m, g = 9.80665 m/s², R = 287.05 J/(kg·K)
		P0_isa = 101325.0
		T0_isa = 288.15
		# Density ratio from pressure ratio (assuming ISA standard atmosphere)
		# ρ/ρ0 = (P/P0)^(1 + L*R/(g*R)) but simplified: ρ/ρ0 ≈ (P/P0)^(g/(R*L)) ≈ (P/P0)^1.235
		# More accurate: use barometric formula ρ = ρ0 * (P/P0)^(1/n) where n≈1.4 for polytropic
		# Simplified: ρ_cas = ρ0 * (P/P0)
		pressure_ratio = static_pressure_pa / P0_isa
		rho_cas = rho_isa * pressure_ratio  # Simplified density correction
		
		CAS_ms = math.sqrt(2.0 * delta_p_pa / rho_cas)
		result['CAS_ms'] = CAS_ms
		result['CAS_kmh'] = CAS_ms * 3.6
		result['CAS_knots'] = CAS_ms * 1.94384
		
		# Calculate TAS (True Airspeed) - uses actual measured density
		temperature_k = temperature_c + 273.15
		
		# Calculate saturation vapor pressure using Magnus formula (in Pa)
		e_sat = 611.2 * math.exp(17.67 * temperature_c / (temperature_c + 243.5))
		vapor_pressure_pa = (humidity_percent / 100.0) * e_sat
		dry_air_pressure_pa = static_pressure_pa - vapor_pressure_pa
		
		# Air density calculation considering humidity
		R_dry = 287.05  # J/(kg·K) for dry air
		R_vapor = 461.495  # J/(kg·K) for water vapor
		
		rho_dry = dry_air_pressure_pa / (R_dry * temperature_k)
		rho_vapor = vapor_pressure_pa / (R_vapor * temperature_k)
		air_density_actual = rho_dry + rho_vapor
		
		TAS_ms = math.sqrt(2.0 * delta_p_pa / air_density_actual)
		result['TAS_ms'] = TAS_ms
		result['TAS_kmh'] = TAS_ms * 3.6
		result['TAS_knots'] = TAS_ms * 1.94384
		
		# Additional info
		result['air_density_isa'] = rho_isa
		result['air_density_cas'] = rho_cas
		result['air_density_actual'] = air_density_actual
		result['air_density_dry'] = rho_dry
		result['air_density_vapor'] = rho_vapor
		result['static_pressure_pa'] = static_pressure_pa
		result['vapor_pressure_pa'] = vapor_pressure_pa
		result['temperature_k'] = temperature_k
		result['humidity_percent'] = humidity_percent
		
	except Exception as e:
		result['error'] = str(e)
		result['IAS_ms'] = 0.0
		result['IAS_kmh'] = 0.0
		result['IAS_knots'] = 0.0
		result['CAS_ms'] = 0.0
		result['CAS_kmh'] = 0.0
		result['CAS_knots'] = 0.0
		result['TAS_ms'] = 0.0
		result['TAS_kmh'] = 0.0
		result['TAS_knots'] = 0.0
	
	return result


# ==== Data store helpers for Web Frontend ====
def _update_shared_store(sensor_data: Dict[str, Any]):
	"""Update global LATEST and SERIES with the newest decoded data."""
	ts = time.time()
	entry: Dict[str, Any] = {"t": ts}
	if "airspeed" in sensor_data:
		air = sensor_data["airspeed"]
		if isinstance(air, dict):
			entry["IAS_ms"] = air.get("IAS_ms")
			entry["IAS_kmh"] = air.get("IAS_kmh")
			entry["CAS_ms"] = air.get("CAS_ms")
			entry["CAS_kmh"] = air.get("CAS_kmh")
			entry["TAS_ms"] = air.get("TAS_ms")
			entry["TAS_kmh"] = air.get("TAS_kmh")
	# Basic sensors (temperature fallback: PADS -> HIDS -> PDUS)
	temp_val = sensor_data.get("temperature_PADS")
	if temp_val is None:
		temp_val = sensor_data.get("temperature_HIDS")
	if temp_val is None:
		temp_val = sensor_data.get("temperature_PDUS")
	entry["temperature_c"] = temp_val
	entry["humidity_percent"] = sensor_data.get("humidity_HIDS")
	entry["pressure_kpa"] = sensor_data.get("pressure_PADS")
	with DATA_LOCK:
		LATEST.clear()
		LATEST.update({
			"timestamp": ts,
			"data": sensor_data,
			"airspeed": sensor_data.get("airspeed", {}),
		})
		SERIES.append(entry)
	# Signal that new data is available
	UPDATE_EVENT.set()



def bytes_to_hex_ascii(data: bytes, parse_protocol: bool = True) -> str:
	"""Return a combined HEX and ASCII view of raw bytes."""
	hex_part = " ".join(f"{b:02X}" for b in data)
	ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
	
	result = f"[{len(data):3d} bytes] {hex_part:<48} | {ascii_part}"
	
	# Add protocol parsing if enabled and valid
	if parse_protocol and len(data) >= 3:
		if data[0] == 0x02 and data[1] == 0x00:
			length = data[2]
			expected_total = 3 + length
			if len(data) == expected_total and len(data) >= 5:
				# Parse data bytes
				data_info = f"\n            協定: Header=02 00, Length={length}, Data={' '.join(f'{b:02X}' for b in data[3:])}"
				
				# Decode sensor data
				sensor_data = decoder(data)
				if sensor_data:
					data_info += "\n            ===== 感測器數據 ====="
					if 'temperature_HIDS' in sensor_data:
						data_info += f"\n            HIDS 溫度: {sensor_data['temperature_HIDS']:7.2f}°C"
					if 'humidity_HIDS' in sensor_data:
						data_info += f"\n            HIDS 濕度: {sensor_data['humidity_HIDS']:7.2f}%"
					if 'pressure_PADS' in sensor_data:
						data_info += f"\n            PADS 壓力: {sensor_data['pressure_PADS']:7.2f} kPa"
					if 'temperature_PADS' in sensor_data:
						data_info += f"\n            PADS 溫度: {sensor_data['temperature_PADS']:7.2f}°C"
					if 'pressure_PDUS' in sensor_data:
						data_info += f"\n            PDUS 差壓: {sensor_data['pressure_PDUS']:7.2f} Pa"
					if 'temperature_PDUS' in sensor_data:
						data_info += f"\n            PDUS 溫度: {sensor_data['temperature_PDUS']:7.2f}°C"
					
					# Display altitude if calculated
					if 'altitude' in sensor_data:
						altitude_info = sensor_data['altitude']
						data_info += "\n            ===== 高度計算 ====="
						if 'pressure_altitude_m' in altitude_info:
							data_info += f"\n            氣壓高度: {altitude_info['pressure_altitude_m']:7.1f} m"
						if 'pressure_altitude_ft' in altitude_info:
							data_info += f" = {altitude_info['pressure_altitude_ft']:7.1f} ft"
						if 'density_altitude_m' in altitude_info:
							data_info += f"\n            密度高度: {altitude_info['density_altitude_m']:7.1f} m"
						if 'density_altitude_ft' in altitude_info:
							data_info += f" = {altitude_info['density_altitude_ft']:7.1f} ft"
						if 'error' in altitude_info:
							data_info += f"\n            計算錯誤: {altitude_info['error']}"
					
					# Display airspeed if calculated
					if 'airspeed' in sensor_data:
						airspeed_info = sensor_data['airspeed']
						data_info += "\n            ===== 空速計算 ====="
						if 'differential_pressure_pa' in airspeed_info:
							data_info += f"\n            差壓 (ΔP): {airspeed_info['differential_pressure_pa']:7.2f} Pa"
						if 'humidity_percent' in airspeed_info:
							data_info += f"\n            使用濕度: {airspeed_info['humidity_percent']:7.1f}%"
						
						# ISA
						if 'IAS_ms' in airspeed_info:
							data_info += f"\n            ISA: {airspeed_info['IAS_ms']:7.2f} m/s"
						if 'IAS_kmh' in airspeed_info:
							data_info += f" = {airspeed_info['IAS_kmh']:7.2f} km/h"
						if 'IAS_knots' in airspeed_info:
							data_info += f" = {airspeed_info['IAS_knots']:7.2f} knots"
						
						# CAS
						if 'CAS_ms' in airspeed_info:
							data_info += f"\n            CAS: {airspeed_info['CAS_ms']:7.2f} m/s"
						if 'CAS_kmh' in airspeed_info:
							data_info += f" = {airspeed_info['CAS_kmh']:7.2f} km/h"
						if 'CAS_knots' in airspeed_info:
							data_info += f" = {airspeed_info['CAS_knots']:7.2f} knots"
						
						# TAS
						if 'TAS_ms' in airspeed_info:
							data_info += f"\n            TAS: {airspeed_info['TAS_ms']:7.2f} m/s"
						if 'TAS_kmh' in airspeed_info:
							data_info += f" = {airspeed_info['TAS_kmh']:7.2f} km/h"
						if 'TAS_knots' in airspeed_info:
							data_info += f" = {airspeed_info['TAS_knots']:7.2f} knots"
						
						# Density info
						if 'air_density_actual' in airspeed_info:
							data_info += f"\n            實際空氣密度: {airspeed_info['air_density_actual']:7.4f} kg/m³"
							if 'air_density_dry' in airspeed_info and 'air_density_vapor' in airspeed_info:
								data_info += f" (乾: {airspeed_info['air_density_dry']:7.4f}, 汽: {airspeed_info['air_density_vapor']:7.4f})"
						
						if 'error' in airspeed_info:
							data_info += f"\n            計算錯誤: {airspeed_info['error']}"
					
					if 'error' in sensor_data:
						data_info += f"\n            解碼錯誤: {sensor_data['error']}"
				
				result += data_info
			elif len(data) == expected_total:
				result += f"\n            協定: Header=02 00, Length={length}, Data={' '.join(f'{b:02X}' for b in data[3:])}"
			else:
				result += f"\n            協定: Header=02 00, Length={length} (期望 {expected_total} bytes, 實際 {len(data)} bytes)"
	
	return result


class App(tk.Tk):
	def __init__(self) -> None:
		super().__init__()
		self.title("UART 接收監視器（協定解析版）")
		self.geometry("1000x600")

		self._q: queue.Queue = queue.Queue()
		self._reader: Optional[SerialReader] = None
		self._auto_reconnect = tk.BooleanVar(value=True)
		self._packet_count = 0  # Track packet numbers
		self._incomplete_count = 0  # Track incomplete packets
		self._discarded_count = 0  # Track discarded bytes

		self._build_ui()
		self._populate_ports()
		self.after(100, self._drain_queue)
		self.protocol("WM_DELETE_WINDOW", self._on_close)

	def _build_ui(self):
		frm_top = ttk.Frame(self)
		frm_top.pack(fill=tk.X, padx=10, pady=10)

		ttk.Label(frm_top, text="COM 連接埠:").pack(side=tk.LEFT)
		self.cmb_port = ttk.Combobox(frm_top, width=20, state="readonly")
		self.cmb_port.pack(side=tk.LEFT, padx=6)

		btn_refresh = ttk.Button(frm_top, text="重新整理", command=self._populate_ports)
		btn_refresh.pack(side=tk.LEFT, padx=6)

		ttk.Label(frm_top, text="鮑率:").pack(side=tk.LEFT, padx=(12, 0))
		self.cmb_baud = ttk.Combobox(frm_top, width=10, state="readonly",
									 values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]) 
		self.cmb_baud.set("115200")
		self.cmb_baud.pack(side=tk.LEFT, padx=6)

		ttk.Label(frm_top, text="封包間隔(ms):").pack(side=tk.LEFT, padx=(12, 0))
		self.spn_timeout = ttk.Spinbox(frm_top, from_=10, to=500, width=8, increment=10)
		self.spn_timeout.set("50")
		self.spn_timeout.pack(side=tk.LEFT, padx=6)

		self.btn_connect = ttk.Button(frm_top, text="連線", command=self._toggle_connect)
		self.btn_connect.pack(side=tk.LEFT, padx=6)

		self.chk_auto_reconnect = ttk.Checkbutton(frm_top, text="自動重連", variable=self._auto_reconnect)
		self.chk_auto_reconnect.pack(side=tk.LEFT, padx=6)

		self.lbl_status_var = tk.StringVar(value="尚未連線")
		ttk.Label(frm_top, textvariable=self.lbl_status_var).pack(side=tk.RIGHT)

		# Text area
		self.txt = ScrolledText(self, wrap=tk.NONE, height=25)
		self.txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
		self.txt.configure(font=("Consolas", 9))
		self.txt.insert(tk.END, "等待資料...\n")
		self.txt.insert(tk.END, "協定格式：[02 00] [長度] [資料...]\n")
		self.txt.insert(tk.END, "範例：02 00 0F 69 56 CF ... (0F=15 表示後面有15 bytes資料)\n")

	def _populate_ports(self):
		ports = []
		if list_ports is not None:
			try:
				ports = [p.device for p in list_ports.comports()]
			except Exception:
				ports = []
		self.cmb_port["values"] = ports
		if ports:
			# Keep previous selection if still present
			current = self.cmb_port.get()
			if current in ports:
				self.cmb_port.set(current)
			else:
				self.cmb_port.current(0)
		else:
			self.cmb_port.set("")

	def _toggle_connect(self):
		if self._reader is None:
			self._connect()
		else:
			self._disconnect()

	def _connect(self):
		port = self.cmb_port.get().strip()
		if not port:
			messagebox.showwarning("提示", "請先選擇 COM 連接埠")
			return
		try:
			baud = int(self.cmb_baud.get())
		except ValueError:
			messagebox.showerror("錯誤", "鮑率必須是數字")
			return
		
		try:
			packet_timeout_ms = float(self.spn_timeout.get())
			packet_timeout = packet_timeout_ms / 1000.0  # Convert to seconds
		except ValueError:
			messagebox.showerror("錯誤", "封包間隔必須是數字")
			return

		try:
			self._reader = SerialReader(
				port=port, 
				baudrate=baud, 
				out_queue=self._q,
				auto_reconnect=self._auto_reconnect.get(),
				max_retries=5,
				retry_interval=2.0,
				packet_timeout=packet_timeout
			)
			self._reader.start()
		except Exception as e:
			self._reader = None
			messagebox.showerror("連線失敗", str(e))
			return

		self._packet_count = 0  # Reset packet counter
		self._incomplete_count = 0
		self._discarded_count = 0
		self.lbl_status_var.set(f"已連線: {port} @ {baud}")
		self.btn_connect.config(text="中斷連線")
		self.cmb_port.config(state="disabled")
		self.cmb_baud.config(state="disabled")
		self.spn_timeout.config(state="disabled")
		self.chk_auto_reconnect.config(state="disabled")

	def _disconnect(self):
		if self._reader is not None:
			try:
				self._reader.stop()
			finally:
				self._reader = None
		self.lbl_status_var.set("尚未連線")
		self.btn_connect.config(text="連線")
		self.cmb_port.config(state="readonly")
		self.cmb_baud.config(state="readonly")
		self.spn_timeout.config(state="normal")
		self.chk_auto_reconnect.config(state="normal")

	def _drain_queue(self):
		# Periodically called in UI thread
		try:
			while True:
				item = self._q.get_nowait()
				if isinstance(item, dict):
					if "error" in item:
						self._append_line(f"[錯誤] {item['error']}")
						if not self._auto_reconnect.get():
							self._disconnect()
					elif "reconnect" in item:
						retry_num = item["reconnect"]
						max_retries = item["max"]
						self._append_line(f"[重連] 嘗試第 {retry_num}/{max_retries} 次重新連線...")
						self.lbl_status_var.set(f"重連中... ({retry_num}/{max_retries})")
					elif "reconnect_success" in item:
						self._append_line(f"[重連] 重新連線成功！")
						port = self.cmb_port.get().strip()
						baud = self.cmb_baud.get()
						self.lbl_status_var.set(f"已連線: {port} @ {baud}")
					elif "reconnect_error" in item:
						self._append_line(f"[重連] 重連失敗: {item['reconnect_error']}")
					elif "reconnect_failed" in item:
						self._append_line(f"[重連] 已達最大重連次數，停止嘗試")
						self._disconnect()
					elif "incomplete" in item:
						self._incomplete_count += 1
						data = item["incomplete"]
						self._append_line(f"[不完整 #{self._incomplete_count}] {bytes_to_hex_ascii(data, parse_protocol=False)}")
					elif "discarded" in item:
						self._discarded_count += 1
						data = item["discarded"]
						self._append_line(f"[丟棄 #{self._discarded_count}] {bytes_to_hex_ascii(data, parse_protocol=False)}")
				elif isinstance(item, (bytes, bytearray)):
					self._packet_count += 1
					b = bytes(item)
					# Update shared store for web
					try:
						sd = decoder(b)
						_update_shared_store(sd)
					except Exception:
						pass
					self._append_line(f"封包 #{self._packet_count}: {bytes_to_hex_ascii(b, parse_protocol=True)}")
		except queue.Empty:
			pass
		self.after(100, self._drain_queue)
	def _append_line(self, text: str):
		self.txt.insert(tk.END, text + "\n")
		self.txt.see(tk.END)

	def _on_close(self):
		try:
			self._disconnect()
		finally:
			self.destroy()


# ================== Flask Web Server ==================
def _create_flask_app() -> Optional["Flask"]:
	"""Create and configure the Flask app if Flask is available."""
	if not _flask_available:
		return None

	app = Flask(__name__)

	@app.get("/")
	def index():
		# Renders templates/dashboard.html
		return render_template("dashboard.html")

	@app.get("/api/live")
	def api_live():
		with DATA_LOCK:
			if not LATEST:
				return jsonify({"status": "no-data"})
			latest = dict(LATEST)
			data_dict = latest.get("data", {}) or {}
			airspeed_dict = latest.get("airspeed", {}) or {}
			altitude_dict = data_dict.get("altitude", {}) or {}

			payload = {
				"timestamp": latest.get("timestamp"),
				"IAS_ms": airspeed_dict.get("IAS_ms"),
				"IAS_kmh": airspeed_dict.get("IAS_kmh"),
				"IAS_knots": airspeed_dict.get("IAS_knots"),
				"CAS_ms": airspeed_dict.get("CAS_ms"),
				"CAS_kmh": airspeed_dict.get("CAS_kmh"),
				"CAS_knots": airspeed_dict.get("CAS_knots"),
				"TAS_ms": airspeed_dict.get("TAS_ms"),
				"TAS_kmh": airspeed_dict.get("TAS_kmh"),
				"TAS_knots": airspeed_dict.get("TAS_knots"),
				"temperature_PADS": data_dict.get("temperature_PADS"),
				"temperature_HIDS": data_dict.get("temperature_HIDS"),
				"temperature_PDUS": data_dict.get("temperature_PDUS"),
				"humidity_percent": data_dict.get("humidity_HIDS"),
				"pressure_kpa": data_dict.get("pressure_PADS"),
				"pressure_altitude_m": altitude_dict.get("pressure_altitude_m"),
				"pressure_altitude_ft": altitude_dict.get("pressure_altitude_ft"),
				"qnh_altitude_m": altitude_dict.get("qnh_altitude_m"),
				"qnh_altitude_ft": altitude_dict.get("qnh_altitude_ft"),
				"altitude": data_dict.get("altitude"),
				"raw": data_dict,
			}
		return jsonify(payload)

	@app.get("/api/series")
	def api_series():
		with DATA_LOCK:
			return jsonify(list(SERIES))
	
	@app.post("/api/set_qnh")
	def set_qnh():
		"""API endpoint to receive QNH pressure setting from frontend."""
		global QNH_PRESSURE
		try:
			data = request.get_json()
			qnh_hpa = data.get('qnh_hpa')
			
			if qnh_hpa is not None and 900 <= qnh_hpa <= 1100:
				QNH_PRESSURE = float(qnh_hpa)
				print(f"[QNH] Updated to {QNH_PRESSURE:.2f} hPa")
				return jsonify({"status": "success", "qnh_hpa": QNH_PRESSURE})
			else:
				return jsonify({"status": "error", "message": "Invalid QNH value"}), 400
		except Exception as e:
			return jsonify({"status": "error", "message": str(e)}), 500
	
	@app.get("/api/get_qnh")
	def get_qnh():
		"""API endpoint to get current QNH setting."""
		return jsonify({"qnh_hpa": QNH_PRESSURE})

	@app.get("/api/stream")
	def api_stream():
		"""Server-Sent Events stream for real-time updates."""
		def event_stream():
			# Send initial data
			with DATA_LOCK:
				if LATEST:
					latest = dict(LATEST)
					data_dict = latest.get("data", {}) or {}
					airspeed_dict = latest.get("airspeed", {}) or {}
					altitude_dict = data_dict.get("altitude", {}) or {}
					payload = {
						"timestamp": latest.get("timestamp"),
						"IAS_ms": airspeed_dict.get("IAS_ms"),
						"IAS_kmh": airspeed_dict.get("IAS_kmh"),
						"IAS_knots": airspeed_dict.get("IAS_knots"),
						"CAS_ms": airspeed_dict.get("CAS_ms"),
						"CAS_kmh": airspeed_dict.get("CAS_kmh"),
						"CAS_knots": airspeed_dict.get("CAS_knots"),
						"TAS_ms": airspeed_dict.get("TAS_ms"),
						"TAS_kmh": airspeed_dict.get("TAS_kmh"),
						"TAS_knots": airspeed_dict.get("TAS_knots"),
						"temperature_PADS": data_dict.get("temperature_PADS"),
						"temperature_HIDS": data_dict.get("temperature_HIDS"),
						"temperature_PDUS": data_dict.get("temperature_PDUS"),
						"humidity_percent": data_dict.get("humidity_HIDS"),
						"pressure_kpa": data_dict.get("pressure_PADS"),
						"pressure_altitude_m": altitude_dict.get("pressure_altitude_m"),
						"pressure_altitude_ft": altitude_dict.get("pressure_altitude_ft"),
						"density_altitude_m": altitude_dict.get("density_altitude_m"),
						"density_altitude_ft": altitude_dict.get("density_altitude_ft"),
					}
					import json
					yield f"data: {json.dumps(payload)}\n\n"
			
			# Stream updates
			while True:
				# Wait for new data (with timeout to detect client disconnect)
				UPDATE_EVENT.wait(timeout=30.0)
				UPDATE_EVENT.clear()
				
				with DATA_LOCK:
					if not LATEST:
						continue
					latest = dict(LATEST)
					data_dict = latest.get("data", {}) or {}
					airspeed_dict = latest.get("airspeed", {}) or {}
					altitude_dict = data_dict.get("altitude", {}) or {}
					payload = {
						"timestamp": latest.get("timestamp"),
						"IAS_ms": airspeed_dict.get("IAS_ms"),
						"IAS_kmh": airspeed_dict.get("IAS_kmh"),
						"IAS_knots": airspeed_dict.get("IAS_knots"),
						"CAS_ms": airspeed_dict.get("CAS_ms"),
						"CAS_kmh": airspeed_dict.get("CAS_kmh"),
						"CAS_knots": airspeed_dict.get("CAS_knots"),
						"TAS_ms": airspeed_dict.get("TAS_ms"),
						"TAS_kmh": airspeed_dict.get("TAS_kmh"),
						"TAS_knots": airspeed_dict.get("TAS_knots"),
						"temperature_PADS": data_dict.get("temperature_PADS"),
						"temperature_HIDS": data_dict.get("temperature_HIDS"),
						"temperature_PDUS": data_dict.get("temperature_PDUS"),
						"humidity_percent": data_dict.get("humidity_HIDS"),
						"pressure_kpa": data_dict.get("pressure_PADS"),
						"pressure_altitude_m": altitude_dict.get("pressure_altitude_m"),
						"pressure_altitude_ft": altitude_dict.get("pressure_altitude_ft"),
						"density_altitude_m": altitude_dict.get("density_altitude_m"),
						"density_altitude_ft": altitude_dict.get("density_altitude_ft"),
					}
					import json
					yield f"data: {json.dumps(payload)}\n\n"
		
		return Response(event_stream(), mimetype='text/event-stream')

	return app


def _start_web_server_background(host: str = "127.0.0.1", port: int = 5000):
	"""Start the Flask development server in a daemon thread."""
	app = _create_flask_app()
	if app is None:
		return

	def _run():
		print(f"[Web] 儀表板啟動中: http://{host}:{port}  (按 Ctrl+點擊開啟)")
		# Disable reloader since we're in a thread
		app.run(host=host, port=port, debug=False, use_reloader=False)

	t = threading.Thread(target=_run, daemon=True)
	t.start()


def main():
	# Optionally start web server in background
	if _flask_available:
		try:
			_start_web_server_background()
		except Exception as _e:
			print(f"[Web] 啟動 Flask 失敗: {_e}")
	else:
		print("[Web] 未安裝 Flask，跳過啟動網頁儀表板。要啟用請安裝 Flask。")

	app = App()
	app.mainloop()


if __name__ == "__main__":
	if serial is None:
		messagebox.showerror("缺少套件", "未找到 pyserial，請先安裝: pip install pyserial")
		sys.exit(1)
	main()

