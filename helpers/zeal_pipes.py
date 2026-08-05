
import psutil
import pywintypes    
import win32file
import threading
import time
import queue
import json

from helpers.zeal_enums import ZealIntEnum, PipeMessageType, LogType, resolve_pipe_value, LabelType


class zeal_pipe_monitor:
    def __init__(self, parent, yaml_data, logger):
        self.parent = parent
        self.yaml_data = yaml_data
        self.logger = logger

        self.running = False
        self.connected_to_zeal = False
        self.thread = None
        self.pipe_handle = None
        self.reconnect_delay = 2

        # Safe communication from worker thread to GUI thread.
        self.raw_message_queue = queue.Queue(maxsize=1000)
        self.parsed_message_queue = queue.Queue(maxsize=1000)
        self.filtered_message_queue = queue.Queue(maxsize=1000)
        self.who_message_queue = queue.Queue(maxsize=1000)

        self.eq_pid = None
        self.pid_manual = None # for testing whe 2 eqs are open - example, I am playing EQL

        self.message_buffer = ""
        self.gui_sink = None
        legacy_sub_types = self._get_yaml_data(
            'zeal_pipes',
            'zeal_types_to_relay_sub',
            [28, 29, 281, 286, 287],
        )
        self.zeal_log_types_to_relay = self._as_int_set(
            self._get_yaml_data(
                'zeal_pipes',
                'zeal_log_types_to_relay',
                legacy_sub_types,
            )
        )
        self.zeal_label_types_to_relay = self._as_int_set(
            self._get_yaml_data(
                'zeal_pipes',
                'zeal_label_types_to_relay',
                [28, 29],
            )
        )
        self.zeal_types_to_relay = self._as_int_set(self._get_yaml_data(
            'zeal_pipes',
            'zeal_types_to_relay_base',
            [
                PipeMessageType.LogText.value,
                PipeMessageType.Label.value,
            ],
        ))

        #self.zeal_enum = ZealIntEnum()
        

    def _get_yaml_data(self, section, key, default=None):
        if self.yaml_data is None:
            return default

        getter = getattr(self.yaml_data, "get_yaml_data", None)
        if callable(getter):
            return getter(section, key, default)

        return default

    @staticmethod
    def _as_int_set(values):
        """Normalize a YAML scalar/list into a set of integer type values."""
        if values is None:
            return set()

        if not isinstance(values, (list, tuple, set)):
            values = [values]

        normalized_values = set()

        for value in values:
            try:
                normalized_values.add(int(value))
            except (TypeError, ValueError):
                continue

        return normalized_values

    def register_gui_sink(self, sink):
        self.gui_sink = sink

    def start(self):

        if self.running:
            self.logger.log_to_file(
                "warning",
                "Zeal pipe monitor is already running.",
            )
            return False

        try:
            if self.pid_manual is None:
                self.eq_pid = self._find_eqgame_pid("eqgame.exe")
            else:
                self.eq_pid = self.pid_manual

           # print(f"eq_pid: {self.eq_pid}")
        except RuntimeError as error:
            self.logger.log_to_file("error", str(error))
            self.show_error(
                self.parent,
                str(error),
                title="EverQuest Not Found",
            )
            return False

        # Set this before starting the thread.
        self.running = True

        self.thread = threading.Thread(
            target=self._monitor_loop,
            args=(self.eq_pid,),
            name="ZealPipeMonitor",
            daemon=True,
        )
        self.thread.start()

        self.logger.log_to_file(
            "info",
            "Zeal pipe monitor started.",
        )
        return True

    def _monitor_loop(self, eq_pid):
        while self.running:
            try:
                self._connect(eq_pid)
                self.connected_to_zeal = True

                while self.running:
                    raw_message = self._read_message()

                    if raw_message is None:
                        break

                    # This is safe from the background thread.
                    self.raw_message_queue.put(raw_message)
                    self.parsed_message_queue.put(self.parse_zeal_message(raw_message))

                    self.filtered_message_queue.put(self.parse_zeal_outer_msg(raw_message))

                   # zeal_parses_msg = self.parse_zeal_message(raw_message)
                    
                    #print(f"parsed: {zeal_parses_msg}")

            except pywintypes_error as error:
                if error.winerror not in (2, 109, 231):
                    self.logger.log_to_file(
                        "error",
                        f"Zeal pipe error: {error}",
                    )

            except Exception as error:
                self.logger.log_to_file(
                    "error",
                    f"Unexpected Zeal pipe error: {error}",
                )

            finally:
                self.connected_to_zeal = False
                self._close_pipe()

            if self.running:
                time.sleep(self.reconnect_delay)

        self.running = False

    def get_pending_raw_messages(self):
        """Return messages waiting for the GUI without blocking."""
        messages = []

        while True:
            try:
                messages.append(
                    self.raw_message_queue.get_nowait()
                )
            except queue.Empty:
                break

        return messages

    def process_pending_messages(self):
        """Drain the worker queues and hand the batch to the GUI sink."""
        batch = []

        while True:
            try:
                raw_message = self.raw_message_queue.get_nowait()
                parsed_message = self.parsed_message_queue.get_nowait()
                filtered_messages = self.filtered_message_queue.get_nowait()
            except queue.Empty:
                break

            batch.append((raw_message, parsed_message, filtered_messages))

        if self.gui_sink is not None and batch:
            self.gui_sink(batch)

        return batch

    def get_pending_parsed_messages(self):
        """Return messages waiting for the GUI without blocking."""
        messages = []

        while True:
            try:
                messages.append(
                    self.parsed_message_queue.get_nowait()
                )
            except queue.Empty:
                break

        return messages    
    
    def get_pending_filtered_messages(self):
        """Return messages waiting for the GUI without blocking."""
        messages = []

        while True:
            try:
                messages.append(
                    self.filtered_message_queue.get_nowait()
                )
            except queue.Empty:
                break

        return messages        
    

    def _read_message(self):
        """
        Read a block of data from the Zeal named pipe.
        """

        try:
            _, raw_data = win32file.ReadFile(
                self.pipe_handle,
                64 * 1024,
            )

            if not raw_data:
                return None

            return raw_data.decode(
                "utf-8",
                errors="replace",
            )

        except pywintypes_error as error:
            if getattr(error, "winerror", None) == 109:
                self.logger.log_to_file(
                    "warning",
                    "Zeal pipe disconnected.",
                )
                return None

            raise
    
    
    def _find_eqgame_pid(self, process_name):
        if psutil is None:
            raise RuntimeError("psutil is not available")

        for process in psutil.process_iter(["pid", "name"]):
            try:
                name = process.info.get("name")

                if (
                    name
                    and name.lower() == process_name.lower()
                ):
                    return process.info["pid"]

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        raise RuntimeError(
            f"{process_name} not found. Is EverQuest running?"
        )

    def _connect(self, eq_pid):
        if win32file is None:
            raise RuntimeError("Windows named-pipe support is not available")

        pipe_path = rf"\\.\pipe\zeal_{eq_pid}"

        self.logger.log_to_file(
            "info",
            f"Connecting to Zeal pipe: {pipe_path}",
        )

        self.pipe_handle = win32file.CreateFile(
            pipe_path,
            win32file.GENERIC_READ,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )

        # self.logger.log_to_file(
        #     "info",
        #     "Connected to Zeal pipe.",
        # )

    def _close_pipe(self):
 
        if self.pipe_handle is None:
            return

        try:
            win32file.CloseHandle(
                self.pipe_handle
            )

        except pywintypes_error:
            pass

        finally:
            self.pipe_handle = None   

    def parse_zeal_outer_msg(self, raw_message):
        parsed_messages = []
        decoder = json.JSONDecoder()

        self.message_buffer += raw_message
        position = 0

        while position < len(self.message_buffer):
            while (
                position < len(self.message_buffer)
                and self.message_buffer[position].isspace()
            ):
                position += 1

            if position >= len(self.message_buffer):
                self.message_buffer = ""
                break

            try:
                outer_data, end_position = decoder.raw_decode(
                    self.message_buffer,
                    position,
                )

            except json.JSONDecodeError as error:
                remaining_data = self.message_buffer[position:]

                # The JSON may be incomplete because the pipe read ended
                # halfway through an object. Keep it for the next read.
                if self._looks_incomplete(
                    remaining_data,
                    error,
                ):
                    self.message_buffer = remaining_data
                    break

                self.logger.log_to_file(
                    "warning",
                    (
                        "Invalid Zeal pipe JSON at position "
                        f"{error.pos}: {error.msg}"
                    ),
                )

                # Try to locate the next JSON object instead of
                # throwing away all remaining data.
                next_object = self.message_buffer.find(
                    "{",
                    position + 1,
                )

                if next_object == -1:
                    self.message_buffer = ""
                    break

                position = next_object
                continue

            position = end_position

            if not isinstance(outer_data, dict):
                self.logger.log_to_file(
                    "warning",
                    "Zeal outer message was not a JSON object.",
                )
                continue

            parsed_message = self._process_outer_message(
                outer_data
            )

            if parsed_message is not None:
                parsed_messages.append(
                    parsed_message
                )

        else:
            # Everything in the buffer was successfully consumed.
            self.message_buffer = ""

        return parsed_messages
    
    def _process_outer_message(self, outer_data):
        """
        Convert one Zeal outer JSON object into a normalized dictionary.

        Outer message categories and their sub-types have separate filters.
        For example:

            1   = Label
            28  = TargetName
            29  = TargetHPPerc
            281 = WhoCommand
            286 = LootMessage
            287 = DiceRoll
        """

        raw_event_type = outer_data.get("type")

        try:
            raw_event_type = int(raw_event_type)
        except (TypeError, ValueError):
            self.logger.log_to_file(
                "warning",
                f"Invalid outer Zeal event type: {raw_event_type}",
            )
            return None

        inner_data = outer_data.get("data")

        if isinstance(inner_data, str):
            try:
                inner_data = json.loads(inner_data)
            except json.JSONDecodeError:
                # Keep normal text as a string.
                pass

        event_type = PipeMessageType.from_value(raw_event_type)
        #print(f"raw_event_type: {raw_event_type}, event_type: {event_type}, inner_data: {inner_data}")
        #print(f"raw_event_type: {raw_event_type}, event_type: {event_type}")

        if raw_event_type not in self.zeal_types_to_relay:
            return None

        #
        # Label messages
        #
        if raw_event_type == PipeMessageType.Label.value:
            # Zeal commonly puts LabelType in the outer "value" field.
            # Also accept the nested layouts emitted by other versions.
            inner_type = outer_data.get("value")

            if isinstance(inner_data, dict):
                inner_type = inner_data.get(
                    "label_type",
                    inner_data.get("type", inner_type),
                )

            elif isinstance(inner_data, list):
                filtered_items = []
                discovered_types = set()

                for item in inner_data:
                    if not isinstance(item, dict):
                        continue

                    item_type = item.get(
                        "label_type",
                        item.get("type"),
                    )

                    try:
                        item_type = int(item_type)
                    except (TypeError, ValueError):
                        continue

                    if item_type in self.zeal_label_types_to_relay:
                        filtered_items.append(item)
                        discovered_types.add(item_type)

                if not filtered_items:
                    return None

                inner_data = filtered_items

                if inner_type is None and discovered_types:
                    inner_type = next(iter(discovered_types))

            try:
                inner_type = int(inner_type)
            except (TypeError, ValueError):
                return None

            if inner_type not in self.zeal_label_types_to_relay:
                return None

            label_type = LabelType.from_value(inner_type)

            return {
                "character": outer_data.get("character"),
                "event_type": raw_event_type,
                "event_type_name": (
                    event_type.name
                    if event_type is not None
                    else "Unknown"
                ),
                "type": inner_type,
                "type_name": (
                    label_type.name
                    if label_type is not None
                    else "Unknown"
                ),
                "data_len": outer_data.get("data_len"),
                "data": inner_data,
            }

        #
        # LogText messages
        #
        if raw_event_type == PipeMessageType.LogText.value:
            inner_type = None

            if isinstance(inner_data, dict):
                inner_type = inner_data.get("type")

            elif isinstance(inner_data, list):
                filtered_items = []
                discovered_types = set()

                for item in inner_data:
                    if not isinstance(item, dict):
                        continue

                    item_type = item.get("type")

                    try:
                        item_type = int(item_type)
                    except (TypeError, ValueError):
                        continue

                    if item_type in self.zeal_log_types_to_relay:
                        filtered_items.append(item)
                        discovered_types.add(item_type)

                if not filtered_items:
                    return None

                inner_data = filtered_items

                if inner_type is None and discovered_types:
                    inner_type = next(iter(discovered_types))

            try:
                if inner_type is not None:
                    inner_type = int(inner_type)
            except (TypeError, ValueError):
                inner_type = None

            if (
                isinstance(inner_data, dict)
                and inner_type not in self.zeal_log_types_to_relay
            ):
                return None

            log_type = LogType.from_value(inner_type)

            return {
                "character": outer_data.get("character"),
                "event_type": raw_event_type,
                "event_type_name": (
                    event_type.name
                    if event_type is not None
                    else "Unknown"
                ),
                "type": inner_type,
                "type_name": (
                    log_type.name
                    if log_type is not None
                    else "Unknown"
                ),
                "data_len": outer_data.get("data_len"),
                "data": inner_data,
            }

        #
        # Ignore non-LogText outer messages when the config contains
        # LogType values such as 281, 286, and 287.
        #
        return None    

    def parse_zeal_message(self, raw_message):
        try:
            message = json.loads(raw_message)

        except json.JSONDecodeError:
            return None

        message_type_value = message.get("type")
        message_type = PipeMessageType.from_value(
            message_type_value
        )

        if message_type is None:
            return {
                "message_type": None,
                "sub_type": None,
                "data": message,
            }

        sub_type_value = message.get("value")

        sub_type = resolve_pipe_value(
            message_type,
            sub_type_value,
        )

        return {
            "message_type": message_type,
            "sub_type": sub_type,
            "data": message,
        }             

    # def should_relay_message(self, message):
    #     message_type = PipeMessageType.from_value(
    #         message.get("type")
    #     )

    #     if message_type != PipeMessageType.LogText:
    #         return False

    #     log_type = LogType.from_value(
    #         message.get("value")
    #     )

    #     if log_type is None:
    #         return False

    #     return log_type.value in self.zeal_types_to_relay            
