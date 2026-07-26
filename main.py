import json
import re
import sys
import time

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QFile, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QTabWidget, QTextBrowser, QPushButton, QTextEdit, QListWidget, QComboBox, QLabel, QProgressBar, QMessageBox
from PySide6.QtGui import QTextCursor

from helpers.zeal_pipes import zeal_pipe_monitor
from helpers.yaml_support import YAMLParser
from helpers.app_state import AppState
from helpers.logging_support import Logger
from helpers.api_factory import APIClient, APIClientError
from windows.player_search import  PlayerSearchWindow
from windows.member_services import MemberServices




class MainWindowApp:

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.window = self._load_window()
        self.timer = QTimer(self.window)
        self.last_who_name_time = None

        ## helpers ##

        self.yaml_data =YAMLParser()

        self.debug_mode = self.yaml_data.get_yaml_data('app_info','general').get('debug_mode')

        logging_console_output = self.yaml_data.get_yaml_data('logging','console_output')
        logging_file = self.yaml_data.get_yaml_data('logging','log_file')
        logging_dir = self.yaml_data.get_yaml_data('logging','path')
        logging_rot_length = self.yaml_data.get_yaml_data('logging','rotation')
        logging_rot_max_days_length = self.yaml_data.get_yaml_data('logging','rotation_max_days')
        
        
        self.logger = Logger(
            log_dir=logging_dir,
            log_file=logging_file,
            console_output=logging_console_output,
            rot_length=logging_rot_length,
            backup_count=logging_rot_max_days_length,
            debug_mode=self.debug_mode,
            window=self.window
        )
        self.logger.configure_logging()    

        self.app_state = AppState(self.logger, self.yaml_data)

        
        self.player_search_window = None
        self.member_services = None

        self.client = APIClient(
                base_url=self.yaml_data.get_yaml_data("app_info", "general").get("lsf_baseurl"),
                api_key= self.yaml_data.get_yaml_data("app_info", "general").get("lsf_apikey"),
            )        

        self._setup_widget_references()
        self._connect_signals()
        self._load_raids_from_api()
        

        self.monitor = None

    def _load_window(self):
        ui_path = Path(__file__).with_name("main_window.ui")
        loader = QUiLoader()
        ui_file = QFile(str(ui_path))

        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Could not open UI file: {ui_path}")

        window = loader.load(ui_file)
        ui_file.close()

        if window is None:
            raise RuntimeError("Failed to load UI file")

        return window
    

    def _setup_widget_references(self):
        self.tab_widget_zeal_output = self.window.findChild(QTabWidget, "zeal_loot_output")
        if self.tab_widget_zeal_output is None:
            raise RuntimeError("Could not find zeal_loot_output tab widget")

        self.text_zeal_output = self.window.findChild(QTextBrowser, "text_zeal_output")
        self.clear_button = self.window.findChild(QPushButton, "button_text_zeal_output_clear")

        self.text_zeal_rolls_output = self.window.findChild(QTextBrowser, "text_zeal_rolls")
        self.clear_rolls_button = self.window.findChild(QPushButton, "button_zeal_rolls_output_clear")


        self.text_zeal_loot_output = self.window.findChild(QTextBrowser, "text_zeal_loot")
        self.clear_loot_button = self.window.findChild(QPushButton, "button_zeal_loot_output_clear")

        self.application_log = self.window.findChild(QProgressBar, "application_log")

        self.text_raid_members = self.window.findChild(QListWidget, "text_raid_members")

        self.raids_scheduled_combo = self.window.findChild(QComboBox, "raids_scheduled_combo")

        self.label_raid_name = self.window.findChild(QLabel,"label_raid_name")
        self.label_raid_id = self.window.findChild(QLabel,"label_raid_id")
        self.label_raid_date = self.window.findChild(QLabel,"label_raid_date")
        self.label_raid_start = self.window.findChild(QLabel,"label_raid_start")
        self.label_raid_end = self.window.findChild(QLabel,"label_raid_end")
        self.label_raid_zone = self.window.findChild(QLabel,"label_raid_zone")

        self.label_currnet_target = self.window.findChild(QLabel, "label_currnet_target")
        self.target_health_bar = self.window.findChild(QProgressBar, "target_health_bar")

        self.label_my_current_zone = self.window.findChild(QLabel, "label_my_current_zone")
        self.label_players_in_zone = self.window.findChild(QLabel, "label_players_in_zone")

        self.button_open_search = self.window.findChild(QPushButton, "button_open_search")
        self.button_update_db_raid = self.window.findChild(QPushButton, "button_update_db_raid")



        self.connect_action = self.window.findChild(QAction, "actionConnect")
        self.disconnect_action = self.window.findChild(QAction, "actionDisconnect")
        self.menu_player_search = self.window.findChild(QAction, "menu_player_search")
        self.menu_member_services = self.window.findChild(QAction, "menu_member_services")




    def _connect_signals(self):
        self.connect_clear_button(self.clear_button, self.text_zeal_output)
        self.connect_clear_button(self.clear_rolls_button, self.text_zeal_rolls_output)
        self.connect_clear_button(self.clear_loot_button, self.text_zeal_loot_output)

        self.menu_player_search.triggered.connect(
            self._open_player_search
        )        

        self.menu_member_services.triggered.connect(
            self._open_member_services
        )

        self.button_open_search.clicked.connect(
            self._open_player_search

        )

        self.button_update_db_raid.clicked.connect(
            self._update_raid_attendance

        )        
        self.raids_scheduled_combo.currentIndexChanged.connect(
                self._populate_raid_details
        )

        self.text_raid_members.itemDoubleClicked.connect(
            self._player_double_clicked
        )
        


        if self.connect_action is not None:
            self.connect_action.triggered.connect(self.connect_to_zeal)
        if self.disconnect_action is not None:
            self.disconnect_action.triggered.connect(self.disconnect_from_zeal)

        self.timer.timeout.connect(self.flush_monitor_messages)
        self.timer.start(250)

    def _update_raid_attendance(self):
        index = self.raids_scheduled_combo.currentIndex()
        if index == -1:
            QMessageBox.critical(
                self.window,
                "Error",
                "You need to select a raid \n before updating the database!.",
            )
            self.logger.log_to_file(
                 "WARNING", 
                    [
                        f"Database was no updated, please select Raid Event first from the dropdown.",
                    ]
                )                        
            return

        data = self.raids_scheduled_combo.itemData(index)
        
        self.selected_raid_event_id = data['id']    

        character_names = [
            self.text_raid_members.item(index).text().strip()
            for index in range(self.text_raid_members.count())
            if self.text_raid_members.item(index).text().strip()
        ]        

        #character_names = ['Bard3', 'Bard4', 'Warrior1']
        try:

            results = self.client.post(
                        "/api/v1/attendance/add",
                        json_data={
                            "raid_event_id": data['id'],
                            "character_names": character_names,
                        }
            )
            
            self.logger.log_to_file(
                    "INFO", 
                        [
                            f"Raid Attendance Update!"
                            f"NOTE: only know characters were updated. Those not on a the guild roster are ignored!",
                            f"Update Info: {json.dumps(results, indent=2)}"
                            ]
                    )  
            QMessageBox.information(
                    self.window,
                    "Raid Attendance Updated",
                    f" {results['raid_event']}: Update - {results['added_count']}, ignored/already in the databse: {results['existing_count']}! \n\n PLEASE review log tab for more details.",
            )                    
            self.app_state.load_app_state()        

        except APIClientError as exc:
                print(exc)        


    def _open_member_services(self):
        # Do not create another copy if it is already open.
        if self.member_services is not None:
            self.member_services.show()
            return

        self.member_services = MemberServices(
            self.yaml_data,
            self.logger,
            self.app_state,
            self.client,
            parent=self.window
        )

        self.member_services.window.destroyed.connect(
            self._member_services_closed
        )        

        self.member_services.show()
        

    def _member_services_closed(self, *_):
        self.member_services = None        


    def _open_player_search(self):
        # Do not create another copy if it is already open.
        if self.player_search_window is not None:
            self.player_search_window.show()
            return

        self.player_search_window = PlayerSearchWindow(
            self.yaml_data,
            self.logger,
            self.app_state,
            parent=self.window
        )

        self.player_search_window.window.destroyed.connect(
            self._player_search_closed
        )        

        self.player_search_window.show()
        

    def _player_search_closed(self, *_):
        self.player_search_window = None

    def _player_search_window_closed(self):
        self.player_search_window = None        


    def _player_double_clicked(self, item):
        player_name = item.text().strip()

        self._open_player_search()


        self.player_search_window.text_player_search.setText(
            player_name
        )

        self.player_search_window.button_search.click()


    def _populate_raid_details(self, index):

        data = self.raids_scheduled_combo.itemData(index)
        
        self.selected_raid_event_id = data['id']
        self.selected_raid_title = data['title']
        self.selected_raid_date = data['date']
        self.selected_raid_start_time = data['start_at']
        self.selected_raid_end_time = data['end_at']
        self.selected_raid_end_zone = data['zone']
        

        self.label_raid_name.setText(self.selected_raid_title)
        self.label_raid_date.setText(self.selected_raid_date)
        self.label_raid_id.setText(str(self.selected_raid_event_id))
        self.label_raid_zone.setText(self.selected_raid_end_zone)
        self.label_raid_start.setText(self.selected_raid_start_time)
        self.label_raid_end.setText(self.selected_raid_end_time)


    def flush_monitor_messages(self):
        if self.monitor is None:
            return

        self.monitor.process_pending_messages()

    def connect_to_zeal(self):
        if self.monitor is not None and self.monitor.running:
            self.text_zeal_output.append("Already connected to Zeal pipe")
        
            self.logger.log_to_file(
                    "info",
                    [
                        f"Already connect to Zeal Pipes"
                    ]
                )                   
            return

        self.monitor = zeal_pipe_monitor(
            self.window,
            self.yaml_data,
            self.logger,
        )
        self.monitor.register_gui_sink(self.handle_pipe_batch)

        try:
            if self.monitor.start():
                self.logger.log_to_file(
                        "info",
                        [
                            f"Connected to Zeal pipe!"
                        ]
                    )                       
                    
            else:
                #self.text_zeal_output.append("Zeal pipe connection was not started")
                self.logger.log_to_file(
                        "info",
                        [
                            f"Zeal pipe connection was not started!",
                            f"Do you have zeal installed?"

                        ]
                    )                       
                                    
        except Exception as error:
            #self.text_zeal_output.append(f"Could not connect to Zeal pipe: {error}")
                self.logger.log_to_file(
                        "ERROR",
                        [
                            f"Could not connect to Zeal pipe with the following error!",
                            f"{error}"

                        ]
                    )                 
            

    def disconnect_from_zeal(self):
        if self.monitor is None:
            return

        if self.monitor.running:
            self.monitor.running = False
            self.monitor._close_pipe()
            
            self.logger.log_to_file(
                    "info",
                    [
                        f"Disconnected from Zeal pipe"
                    ]
                )                     
            
        else:
            
            self.logger.log_to_file(
                    "info",
                    [
                        f"Zeal pipe is not connected"
                    ]
                )                

    def handle_pipe_batch(self, batch):
        #print(batch)
        for raw_message, parsed_message, filtered_messages in batch:
            self._route_messages(filtered_messages or [parsed_message])

    def _route_messages(self, messages):
        for message in messages:
            if not isinstance(message, dict):
                continue

            numeric_type = self._get_message_type(message)
            if numeric_type == 28 or numeric_type == 29:
               self._target_message_parse(message)

                


            if numeric_type == 281:
                self._display_who_members(message)
                continue

            if numeric_type == 287:
                print(message)
                if message and "a magic die is rolled by" in str(message).lower():
                    continue
                standard_clean= self._format_message(message)
                
                target = self.text_zeal_rolls_output
                target.append(self._format_message(message, type="287"))
                print(f"message {message}")
            elif numeric_type == 286:
                target = self.text_zeal_loot_output
                target.append(self._format_message(message))
            else:
                target = self.text_zeal_output
                target.append(self._format_message(message))

            #target.append(self._format_message(message))

    # def _target_message_parse(self, message):
    #         data = message.get("data") if isinstance(message, dict) else None
    #         numeric_type = self._get_message_type(message)
    #         if numeric_type == 28 or numeric_type == 29:
    #             self.label_currnet_target.setText(data[0]['value'])
    #             self.target_health_bar.setValue(int(data[1]['value']))                

    def _target_message_parse(self, message):
        if not isinstance(message, dict):
            return

        data = message.get("data")
        numeric_type = self._get_message_type(message)

        if numeric_type not in (28, 29):
            return

        if not isinstance(data, list) or len(data) < 2:
            return

        if not isinstance(data[0], dict) or not isinstance(data[1], dict):
            return

        target_name = data[0].get("value")
        health_value = data[1].get("value")

        if target_name:
            self.label_currnet_target.setText(str(target_name))

        try:
            health = int(health_value)
        except (TypeError, ValueError):
            return

        self.target_health_bar.setValue(health)    


    def _get_message_type(self, message):
        if not isinstance(message, dict):
            return None

        message_type = message.get("type")
        try:
            return int(message_type)
        except (TypeError, ValueError):
            pass

        data = message.get("data")
        return self._find_nested_message_type(data)
        

    def _find_nested_message_type(self, value):
        if isinstance(value, dict):
            for key in ("type", "sub_type", "message_type"):
                try:
                    return int(value.get(key))
                except (TypeError, ValueError):
                    continue

            for child in value.values():
                nested_type = self._find_nested_message_type(child)
                if nested_type is not None:
                    return nested_type
        elif isinstance(value, list):
            for item in value:
                nested_type = self._find_nested_message_type(item)
                if nested_type is not None:
                    return nested_type

        return None

    def _display_who_members(self, message):
       # names = self._extract_who_names(message)
        #
        data = message.get("data") if isinstance(message, dict) else None
        match = re.search(r"\]\s+([^(<]+?)\s*(?:\(|<|$)", data['text'])
        name = match.group(1).strip() if match else None

        match = re.search(
            r"There (?:are|is) (?P<count>\d+) players? in (?P<zone>.+?)\.$",
            message["data"]["text"],
        )
        if match:
            self.label_my_current_zone.setText(match.group("zone"))
            self.label_players_in_zone.setText(match.group("count"))
                    


        current_time = time.monotonic()

        if self.last_who_name_time is  None:
            self.last_who_name_time = time.monotonic()

        if self.last_who_name_time is not None:
            elapsed = current_time - self.last_who_name_time

            #print(f"Seconds since last name: {elapsed:.2f}")

            self.last_who_name_time = time.monotonic()


            if elapsed > 5:
                self.text_raid_members.clear()


        #print(f"data: {data}")
        #print(f"data[text]: {data['text']}")
        #print(f"matrch {match}")
        #print(f"name {name}")
        if name:
            self.text_raid_members.addItem(name)

    def _format_message(self, message, type=None):
        if not isinstance(message, dict):
            return str(message)

        character = message.get("character") or "Zeal"
        type_name = message.get("type_name") or "Message"
        data = message.get("data")

        if isinstance(data, dict):
            text = data.get("text") or data.get("message") or data.get("content")
            if text:
                data_text = str(text)
            else:
                data_text = json.dumps(data, ensure_ascii=False, sort_keys=True)
        elif isinstance(data, list):
            data_text = json.dumps(data, ensure_ascii=False, sort_keys=True)
        elif data is None:
            data_text = ""
        else:
            data_text = str(data)

        data_text = self._clean_text(data_text, character, type)

        if data_text:
            return f"[{type_name}] {character}: {data_text}"
        return f"[{type_name}] {character}"

    def _clean_text(self, text, character=None, type=None):
        cleaned = str(text).strip()
        cleaned = cleaned.replace("**", "")
        cleaned = cleaned.replace("--", "")

        if character:
            cleaned = cleaned.replace("You have looted a ", f"{character} has looted ")
            cleaned = cleaned.replace("You have looted ", f"{character} has looted ")
        else:
            cleaned = cleaned.replace("You have looted a ", "You have looted ")

        if type == "287":  #rolls
            match = re.search(
                r"number from (\d+) to (\d+).*turned up a (\d+)",
                cleaned,
            )
            if match:
                minimum, maximum, rolled = map(int, match.groups())    
                cleaned = f"Rolled between {minimum} and {maximum}, turned up a {rolled} "        


        else:

            cleaned = re.sub(r"\d+(?=\s*[A-Za-z])", "", cleaned)
            #print(f"clean1: {cleaned}")
            cleaned = re.sub(r"\b\d{4,}\b", "", cleaned)
            #print(f"clean2: {cleaned}")
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            #print(f"clean3 {cleaned}")
            cleaned = cleaned.strip(".- ")
            #print(f"clean4 {cleaned}")

        return cleaned

    def _load_raids_from_api(self):
        try:
            for raids in self.app_state.raid_scheduled:
                formatted_date = datetime.fromisoformat(
                        raids['start_at'].replace("Z", "+00:00")
                    ).strftime("%m/%d/%Y")  
                formatted_time_start = datetime.fromisoformat(
                        raids['start_at'].replace("Z", "+00:00")
                    ).strftime("%I:%M %p")     
                formatted_time_end = datetime.fromisoformat(
                        raids['end_at'].replace("Z", "+00:00")
                    ).strftime("%I:%M %p")                   
                            
                self.raids_scheduled_combo.addItem(f"{raids['title']} -  {formatted_date}", 
                                                {
                                                        "id": raids['id'],
                                                        "title": raids['title'],
                                                        "start_at": formatted_time_start,
                                                        "end_at":formatted_time_end,
                                                        "zone": raids['zone'],
                                                        "date": formatted_date
                                                    }
                                                )
        except Exception as e:
            self.logger.log_to_file(
                    "CRITICAL",
                    [
                        f"Appliaction loading error!!", 
                        f"ERROR: {e}"
                    ]
                )                

   

    def connect_clear_button(self, button, widget):
        if button is not None and widget is not None:
            button.clicked.connect(widget.clear)

    def show(self):
        self.window.show()

    def run(self):
        return self.app.exec()


def main():
    app = MainWindowApp()
    app.show()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
