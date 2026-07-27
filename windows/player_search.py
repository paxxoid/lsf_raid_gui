from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget, 
    QCompleter,
    QTableWidgetItem
)

from helpers.app_state import AppState
from windows.member_services import MemberServices



class PlayerSearchWindow:
    def __init__(self,  yaml_data, logger, app_state, api_client, parent=None,):
        self.window = self._load_window(parent)
        self.yaml_data = yaml_data
        self.logger = logger
        self.app_state = app_state
        self.api_client = api_client

        self._setup_widget_references()
        self._connect_signals()
        self._load_player_combo()
        self._setup_player_search()
        self.member_services = None


    def _setup_widget_references(self):        
        ## player info
        self.label_member_name = self.window.findChild(QLabel, "label_member_name")
        self.label_member_class = self.window.findChild(QLabel, "label_member_class")
        self.label_member_type = self.window.findChild(QLabel, "label_member_type")
        self.label_member_joined = self.window.findChild(QLabel, "label_member_joined")
        self.label_member_level = self.window.findChild(QLabel, "label_member_level")
        self.label_member_main = self.window.findChild(QLabel, "label_member_main")
        self.label_member_rank = self.window.findChild(QLabel, "label_member_rank")
        self.label_member_raids_attended = self.window.findChild(QLabel, "label_member_raids_attended")
        self.label_member_last_raid = self.window.findChild(QLabel, "label_member_last_raid")
        self.label_member_loot_awarded = self.window.findChild(QLabel, "label_member_loot_awarded")
        self.label_member_last_looted = self.window.findChild(QLabel, "label_member_last_looted")
        self.label_no_records_found = self.window.findChild(QLabel, "label_no_records_found")
        self.button_not_found_adduser = self.window.findChild(QPushButton, "button_not_found_adduser")
        


        ## seafch area
        self.text_player_search = self.window.findChild(QLineEdit, "text_player_search")
        self.combo_player_select = self.window.findChild(QComboBox, "combo_player_select")
        self.button_search = self.window.findChild(QPushButton, "button_search")
        self.button_clear = self.window.findChild(QPushButton, "button_clear")

        ##tables
        self.tbl_attendance = self.window.findChild(QTableWidget, "tbl_attendance")
        self.tbl_loot = self.window.findChild(QTableWidget, "tbl_loot")


        self.label_member_name.setText("test")
        
    def _connect_signals(self):

        ## for atio complete
        player_names = [
            player["character_name"]
            for player in self.app_state.PLAYER_RECORDS
        ]
        self.player_completer = QCompleter(
            player_names,
            self.window,
        )
        self.player_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.player_completer.setFilterMode(
            Qt.MatchFlag.MatchContains
        )
        self.player_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.text_player_search.setCompleter(
            self.player_completer
        )        
        self.player_completer.activated[str].connect(
            self._player_selected
        )        
        ## end auito compelte

        self.button_clear.clicked.connect(
            self._clear_player_search
        )

        self.button_search.clicked.connect(
            self._search_player
        )

        self.button_not_found_adduser.clicked.connect(
            self._not_found_button
        )



        self.label_no_records_found.hide()
        self.button_not_found_adduser.hide()

    def _not_found_button(self):
        player_name = self.text_player_search.text().strip()

        self._open_member_services()

        self.member_services.text_character_name.setText(
                player_name
            )
        
    def _open_member_services(self):
        # Do not create another copy if it is already open.
        if self.member_services is not None:
            self.member_services.show()
            return

        self.member_services = MemberServices(
            self.yaml_data,
            self.logger,
            self.app_state,
            self.api_client,
            parent=self.window
        )

        self.member_services.window.destroyed.connect(
            self._member_services_closed
        )        

        self.member_services.show()

    def _member_services_closed(self, *_):
        self.member_services = None                       


    def _search_player(self):

        self.label_no_records_found.hide()
        self.button_not_found_adduser.hide()
        if  (not self.text_player_search.text().strip()
            and self.combo_player_select.currentText() == "Select Member"):
            return
        if self.text_player_search.text().strip():
            search_player =  self.text_player_search.text().strip()
            self.combo_player_select.setCurrentIndex(0)

        if (not self.text_player_search.text().strip()
            and self.combo_player_select.currentText() != "Select Member"): 
            search_player =  self.combo_player_select.currentText()

        

        selected_player = next(
            filter(
                lambda player: (
                    player.get("character_name", "").lower()
                    == search_player.lower()
                ),
                self.app_state.PLAYER_RECORDS,
            ),
            None,
        )

        if selected_player is None:
            self.label_no_records_found.show()
            self.button_not_found_adduser.show()
            return

        player_loot_records =  list(filter(lambda record: record.get("member_id") == selected_player.get("id"), self.app_state.loot_records))
        player_raid_attendence = list(filter(lambda record: record.get("member_id") == selected_player.get("id"), self.app_state.raid_attendance))   
        most_recent_loot = max(player_loot_records, key=lambda record: datetime.fromisoformat(record["awarded_at"].replace("Z", "+00:00")),default=None,)    

        if most_recent_loot:
            most_recent_date = datetime.fromisoformat(
                most_recent_loot["awarded_at"].replace("Z", "+00:00")
            ).strftime("%m/%d/%Y")
        else:
            most_recent_date = "No loot records"      

        joined_date = datetime.fromisoformat(
               selected_player["joined_at"].replace("Z", "+00:00")
            ).strftime("%m/%d/%Y")

        self.member_id_number = selected_player["id"]
        self.label_member_name.setText(selected_player["character_name"])
        self.label_member_class.setText(selected_player["class_name_display"])
        self.label_member_type.setText(selected_player["character_type"])
        self.label_member_joined.setText(joined_date)
        self.label_member_level.setText(str(selected_player["level"]))
        self.label_member_main.setText(selected_player["main_character"])
        self.label_member_rank.setText(selected_player["rank_display"])
        self.label_member_raids_attended.setText(str(len(player_raid_attendence)))
        self.label_member_last_raid.setText(selected_player["last_raid_attended"])
        self.label_member_loot_awarded.setText(str(len(player_loot_records)))
        self.label_member_last_looted.setText(most_recent_date)


        self.tbl_attendance.setRowCount(len(player_raid_attendence))
        for row, record in enumerate(player_raid_attendence, start=0):
            raid_date = datetime.fromisoformat(
                    record["raid_date"].replace("Z", "+00:00")
                    ).strftime("%m/%d/%Y")

            

            self.tbl_attendance.setItem(
                row,
                0,
               self._centered_item(str(record["raid_event_id"])),
             )

            self.tbl_attendance.setItem(
                row,
                1,
               self._centered_item(str(record["raid_event"])),
             )   
            self.tbl_attendance.setItem(
                row,
                2,
               self._centered_item(str(record["zone"])),
             )    
            self.tbl_attendance.setItem(
                row,
                3,
               self._centered_item(str(raid_date)),
             )            

            self.tbl_attendance.setItem(
                row,
                4,
               self._centered_item(str(record["arrival_time"])),
             )    
            self.tbl_attendance.setItem(
                row,
                5,
               self._centered_item(str(record["notes"])),
             )             

        
        self.tbl_loot.setRowCount(len(player_loot_records))
        for row, record in enumerate(player_loot_records, start=0):
            looted_date = datetime.fromisoformat(
                    record["awarded_at"].replace("Z", "+00:00")
                    ).strftime("%m/%d/%Y")

            

            self.tbl_loot.setItem(
                row,
                0,
               self._centered_item(str(record["raid_event"])),
             )

            self.tbl_loot.setItem(
                row,
                1,
               self._centered_item(str(record["zone"])),
             )   
            self.tbl_loot.setItem(
                row,
                2,
               self._centered_item(str(record["item_name"])),
             )    
            self.tbl_loot.setItem(
                row,
                3,
               self._centered_item(str(looted_date)),
             )            

            self.tbl_loot.setItem(
                row,
                4,
               self._centered_item(str(record["toon_type_display"])),
             )    
            self.tbl_loot.setItem(
                row,
                5,
               self._centered_item(str(record["notes"])),
             )                                
                               

                     

    def _centered_item(self, value):
        item = QTableWidgetItem(
            "" if value is None else str(value)
        )
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
        

    def _clear_player_search(self):
        self.text_player_search.clear()
        self.text_player_search.setFocus()        

        self.combo_player_select.setCurrentIndex(0)

        self.label_member_name.setText("")
        self.label_member_class.setText("")
        self.label_member_type.setText("")
        self.label_member_joined.setText("")
        self.label_member_level.setText("")
        self.label_member_main.setText("")
        self.label_member_rank.setText("")
        self.label_member_raids_attended.setText("")
        self.label_member_last_raid.setText("")
        self.label_member_loot_awarded.setText("")
        self.label_member_last_looted.setText("")



    def _load_player_combo(self):
        self.combo_player_select.insertItem(0, "Select Member", None)
        for  player in self.app_state.PLAYER_RECORDS:
           # print(player)
            player_data = {
                "id": player["id"],
                "character_name": player["character_name"],
                "character_type": player["character_type"],
                "character_type_display": player["character_type_display"],
                "main_character_id": player["main_character_id"],
                "main_character": player["main_character"],
                "class_name": player["class_name"],
                "class_name_display": player["class_name_display"],
                "race": player["race"],
                "level": player["level"],
                "rank": player["rank"],
                "rank_display": player["rank_display"],
                "active": player["active"],
                "raider": player["raider"],
                "featured": player["featured"],
                "joined_at": player["joined_at"],
                "bio": player["bio"],
                "last_raid_attended": player["last_raid_attended"],
            }            
            self.combo_player_select.addItem(f"{player['character_name']}", 
                                            player_data
   
                                    )      

    def _player_selected(self, player_name):
        player = next(
            (
                player
                for player in self.app_state.PLAYER_RECORDS
                if player["character_name"].lower()
                == player_name.lower()
            ),
            None,
        )

        if player is None:
            return

        self.selected_player = player
        self.selected_player_id = player["id"]

        print(self.selected_player)


    def _setup_player_search(self):
        self.text_player_search = self.window.findChild(
            QLineEdit,
            "text_player_search",
        )

        if self.text_player_search is None:
            raise RuntimeError(
                "text_player_search was not found"
            )

        player_names = [
            player["character_name"]
            for player in self.app_state.PLAYER_RECORDS
        ]

        self.player_completer = QCompleter(
            player_names,
            self.window,
        )

        self.player_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )

        self.player_completer.setFilterMode(
            Qt.MatchFlag.MatchContains
        )

        self.text_player_search.setCompleter(
            self.player_completer
        )

        self.player_completer.activated[str].connect(
            self._player_selected
        )                

    def _load_window(self, parent=None):
        ui_path = Path(__file__).with_name(
            "player_search.ui"
        )

        loader = QUiLoader()
        ui_file = QFile(str(ui_path))

        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            raise RuntimeError(
                f"Could not open UI file: {ui_path}"
            )

        window = loader.load(ui_file, parent)
        ui_file.close()

        if window is None:
            raise RuntimeError(
                "Failed to load player search UI"
            )

        # Completely destroy the window when closed.
        window.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )

        return window

    def show(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()    



